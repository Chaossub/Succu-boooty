import logging
import pytz
from datetime import datetime, timedelta
from pyrogram import filters
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

logger = logging.getLogger(__name__)

# Mongo client & DB setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client[os.getenv("MONGO_DB_NAME", "SuccuBot")]
flyers_col = db.flyers
scheduled_col = db.scheduled_flyers

# Helper: restore scheduled jobs on startup
def restore_jobs(app, scheduler):
    logger.info("[restore_jobs] Loading scheduled flyers...")
    count = 0
    for job in scheduled_col.find({}):
        # Skip old/corrupt jobs
        if not all(x in job for x in ("chat_id", "flyer_name", "run_time")):
            logger.warning(f"[restore_jobs] Skipping job {job.get('_id')} (missing fields)")
            continue
        try:
            run_time = job["run_time"]
            # Flexible time string parsing: allow both with and without timezone
            try:
                run_time_obj = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
            except Exception:
                run_time_obj = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
                # Assume LA time
                la_tz = pytz.timezone("America/Los_Angeles")
                run_time_obj = la_tz.localize(run_time_obj)
            scheduler.add_job(
                send_flyer_job,
                "date",
                run_date=run_time_obj,
                args=[app, job["chat_id"], job["flyer_name"]],
                id=str(job["_id"])
            )
            count += 1
        except Exception as e:
            logger.error(f"[restore_jobs] Error restoring job: {e}")
    logger.info(f"[restore_jobs] Restored {count} scheduled flyer jobs.")

async def send_flyer_job(app, chat_id, flyer_name):
    flyer = flyers_col.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        logger.warning(f"Flyer '{flyer_name}' not found for chat {chat_id}")
        return
    try:
        await app.send_photo(
            chat_id=chat_id,
            photo=flyer["file_id"],
            caption=flyer.get("caption", "")
        )
    except Exception as e:
        logger.error(f"Failed to send scheduled flyer: {e}")

# ----- Handler Functions -----

async def addflyer_handler(client, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to an image with /addflyer <name> <caption>")
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        return await message.reply("Usage: /addflyer <name> <caption>")
    name = args[1]
    caption = args[2] if len(args) > 2 else ""
    file_id = message.reply_to_message.photo.file_id
    flyers_col.replace_one(
        {"chat_id": message.chat.id, "name": name},
        {
            "chat_id": message.chat.id,
            "name": name,
            "file_id": file_id,
            "caption": caption,
        },
        upsert=True,
    )
    await message.reply(f"✅ Flyer '{name}' saved.")

async def changeflyer_handler(client, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to a new image with /changeflyer <name>")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("Usage: /changeflyer <name>")
    name = args[1]
    file_id = message.reply_to_message.photo.file_id
    result = flyers_col.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": file_id}},
    )
    if result.matched_count:
        await message.reply(f"✅ Flyer '{name}' image updated.")
    else:
        await message.reply(f"❌ Flyer '{name}' not found.")

async def deleteflyer_handler(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("Usage: /deleteflyer <name>")
    name = args[1]
    result = flyers_col.delete_one({"chat_id": message.chat.id, "name": name})
    if result.deleted_count:
        await message.reply(f"✅ Flyer '{name}' deleted.")
    else:
        await message.reply(f"❌ Flyer '{name}' not found.")

async def listflyers_handler(client, message):
    flyers = list(flyers_col.find({"chat_id": message.chat.id}))
    if not flyers:
        await message.reply("No flyers found for this group.")
        return
    flyer_list = "\n".join(f"• {f['name']}" for f in flyers)
    await message.reply(f"📋 Flyers:\n{flyer_list}")

async def scheduleflyer_handler(client, message):
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        return await message.reply("Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> (24h, LA time)")
    flyer_name = args[1]
    date_str = args[2]
    time_str = args[3]
    try:
        la_tz = pytz.timezone("America/Los_Angeles")
        dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        run_time = la_tz.localize(dt_naive)
    except Exception as e:
        return await message.reply(f"Invalid date/time. {e}")
    # Save scheduled job to DB
    doc = {
        "chat_id": message.chat.id,
        "flyer_name": flyer_name,
        "run_time": run_time.strftime("%Y-%m-%d %H:%M:%S%z"),
    }
    result = scheduled_col.insert_one(doc)
    # Add to scheduler
    message._client.scheduler.add_job(
        send_flyer_job,
        "date",
        run_date=run_time,
        args=[client, message.chat.id, flyer_name],
        id=str(result.inserted_id)
    )
    await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {run_time.strftime('%Y-%m-%d %H:%M %Z')}")

async def cancelflyer_handler(client, message):
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        return await message.reply("Usage: /cancelflyer <flyer_name>")
    flyer_name = args[1]
    removed = 0
    for job in scheduled_col.find({"chat_id": message.chat.id, "flyer_name": flyer_name}):
        job_id = str(job["_id"])
        client.scheduler.remove_job(job_id)
        scheduled_col.delete_one({"_id": job["_id"]})
        removed += 1
    if removed:
        await message.reply(f"✅ Cancelled {removed} scheduled flyer(s) named '{flyer_name}'.")
    else:
        await message.reply(f"❌ No scheduled flyers found with that name.")

# ----- Registration -----

def register(app, scheduler):
    logger.info("Registering flyer_scheduler...")
    app.scheduler = scheduler
    restore_jobs(app, scheduler)

    @app.on_message(filters.command("addflyer"))
    async def _(client, message):
        await addflyer_handler(client, message)

    @app.on_message(filters.command("changeflyer"))
    async def _(client, message):
        await changeflyer_handler(client, message)

    @app.on_message(filters.command("deleteflyer"))
    async def _(client, message):
        await deleteflyer_handler(client, message)

    @app.on_message(filters.command("listflyers"))
    async def _(client, message):
        await listflyers_handler(client, message)

    @app.on_message(filters.command("scheduleflyer"))
    async def _(client, message):
        await scheduleflyer_handler(client, message)

    @app.on_message(filters.command("cancelflyer"))
    async def _(client, message):
        await cancelflyer_handler(client, message)
