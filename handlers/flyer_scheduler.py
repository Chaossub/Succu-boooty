import os
import logging
from datetime import datetime
from pymongo import MongoClient
from pyrogram import filters, types
from pyrogram.errors import ChatAdminRequired
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Logging Setup ────────────────────────────────────────────────
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ─── ENV and Mongo ───────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")
SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
LA_TZ = timezone(SCHED_TZ)

mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers = mongo.flyers
flyer_schedules = mongo.flyer_schedules

# ─── Helper Functions ─────────────────────────────────────────────
def is_admin(app, chat_id, user_id):
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def send_flyer(app, chat_id, flyer_name):
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        logger.error(f"[send_flyer] Flyer not found: {flyer_name} in {chat_id}")
        return
    try:
        await app.send_photo(
            chat_id,
            flyer["file_id"],
            caption=flyer.get("caption", ""),
            parse_mode="HTML",
        )
        logger.info(f"Sent flyer '{flyer_name}' to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send flyer '{flyer_name}' to {chat_id}: {e}")

# ─── Flyer Management Commands ────────────────────────────────────
async def addflyer_handler(app, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("❌ Reply to a photo to use this command.")

    if not is_admin(app, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can add flyers.")

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("❌ Usage: /addflyer <flyer_name> <caption> (as reply to photo)")

    flyer_name, caption = args[1], args[2]
    file_id = message.reply_to_message.photo.file_id

    flyers.update_one(
        {"chat_id": message.chat.id, "name": flyer_name},
        {"$set": {"file_id": file_id, "caption": caption}},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{flyer_name}' added/updated.")

async def changeflyer_handler(app, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("❌ Reply to a new photo to use this command.")

    if not is_admin(app, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can change flyers.")

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("❌ Usage: /changeflyer <flyer_name> <caption> (as reply to photo)")

    flyer_name, caption = args[1], args[2]
    file_id = message.reply_to_message.photo.file_id

    flyers.update_one(
        {"chat_id": message.chat.id, "name": flyer_name},
        {"$set": {"file_id": file_id, "caption": caption}},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{flyer_name}' changed.")

async def deleteflyer_handler(app, message):
    if not is_admin(app, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete flyers.")

    args = message.text.split()
    if len(args) < 2:
        return await message.reply("❌ Usage: /deleteflyer <flyer_name>")

    flyer_name = args[1]
    flyers.delete_one({"chat_id": message.chat.id, "name": flyer_name})
    await message.reply(f"✅ Flyer '{flyer_name}' deleted.")

async def listflyers_handler(app, message):
    fs = flyers.find({"chat_id": message.chat.id})
    names = [f"- <b>{f['name']}</b>: {f.get('caption', '')[:30]}" for f in fs]
    if names:
        await message.reply("<b>Flyers in this group:</b>\n" + "\n".join(names))
    else:
        await message.reply("No flyers found.")

# ─── Flyer Scheduler Commands ─────────────────────────────────────
async def scheduleflyer_handler(app, message):
    if not is_admin(app, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")

    args = message.text.split(maxsplit=4)
    if len(args) < 5:
        return await message.reply(
            "❌ Usage: /scheduleflyer <target_group_id> <flyer_name> <YYYY-MM-DD> <HH:MM> (24h Los Angeles time)\n"
            "Example: /scheduleflyer -1001234567890 tipping 2025-07-18 17:00"
        )
    try:
        target_chat_id = int(args[1])
        flyer_name = args[2]
        run_date_str = args[3] + " " + args[4]
        run_time = LA_TZ.localize(datetime.strptime(run_date_str, "%Y-%m-%d %H:%M"))
        now = datetime.now(LA_TZ)
        if run_time <= now:
            return await message.reply("❌ Time must be in the future (LA time).")
    except Exception as e:
        logger.error(f"[scheduleflyer] Error parsing args: {e}")
        return await message.reply("❌ Invalid date/time format.")

    # Save to DB and schedule job
    job_doc = {
        "chat_id": target_chat_id,
        "flyer_name": flyer_name,
        "run_time": run_time.strftime("%Y-%m-%d %H:%M:%S%z"),
        "scheduled_by": message.from_user.id,
    }
    flyer_schedules.insert_one(job_doc)

    # Register job with scheduler
    def runner():
        try:
            app.loop.create_task(send_flyer(app, target_chat_id, flyer_name))
        except Exception as e:
            logger.error(f"[scheduleflyer_runner] {e}")

    app.scheduler.add_job(
        runner,
        "date",
        run_date=run_time,
        id=f"flyer_{flyer_name}_{target_chat_id}_{int(run_time.timestamp())}"
    )

    await message.reply(
        f"✅ Flyer '{flyer_name}' scheduled for group <code>{target_chat_id}</code> at <b>{run_time.strftime('%Y-%m-%d %H:%M %Z')}</b>."
    )

async def cancelflyer_handler(app, message):
    if not is_admin(app, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can cancel scheduled flyers.")

    args = message.text.split()
    if len(args) < 3:
        return await message.reply("❌ Usage: /cancelflyer <flyer_name> <group_id>")
    flyer_name, chat_id = args[1], int(args[2])

    jobs = list(flyer_schedules.find({"chat_id": chat_id, "flyer_name": flyer_name}))
    if not jobs:
        return await message.reply("❌ No scheduled flyer found with that name for that group.")

    for job in jobs:
        try:
            sched_id = f"flyer_{flyer_name}_{chat_id}_{int(datetime.strptime(job['run_time'], '%Y-%m-%d %H:%M:%S%z').timestamp())}"
            app.scheduler.remove_job(sched_id)
        except Exception as e:
            logger.warning(f"Failed to remove job {sched_id}: {e}")
        flyer_schedules.delete_one({"_id": job["_id"]})
    await message.reply(f"✅ Cancelled scheduled flyer '{flyer_name}' for group {chat_id}.")

# ─── Restore Jobs on Startup ──────────────────────────────────────
def restore_jobs(app, scheduler):
    logger.info("[restore_jobs] Loading scheduled flyers...")
    jobs = list(flyer_schedules.find({}))
    logger.info(f"[restore_jobs] Found {len(jobs)} scheduled flyers in DB.")
    for job in jobs:
        run_time = job.get("run_time")
        chat_id = job.get("chat_id")
        flyer_name = job.get("flyer_name")
        if not run_time or not chat_id or not flyer_name:
            logger.warning(f"[restore_jobs] Skipping job {job.get('_id')} (missing fields)")
            continue
        try:
            dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
            def runner():
                try:
                    app.loop.create_task(send_flyer(app, chat_id, flyer_name))
                except Exception as e:
                    logger.error(f"[restore_jobs.runner] {e}")

            sched_id = f"flyer_{flyer_name}_{chat_id}_{int(dt.timestamp())}"
            scheduler.add_job(
                runner,
                "date",
                run_date=dt,
                id=sched_id,
            )
        except Exception as e:
            logger.error(f"[restore_jobs] Error restoring job: {e}")

    logger.info("Restored scheduled flyer jobs.")

# ─── Register All Commands ────────────────────────────────────────
def register(app, scheduler: AsyncIOScheduler):
    logger.info("Registering flyer_scheduler...")
    app.scheduler = scheduler

    restore_jobs(app, scheduler)

    app.add_handler(filters.command("addflyer")(lambda c, m: addflyer_handler(c, m)))
    app.add_handler(filters.command("changeflyer")(lambda c, m: changeflyer_handler(c, m)))
    app.add_handler(filters.command("deleteflyer")(lambda c, m: deleteflyer_handler(c, m)))
    app.add_handler(filters.command("listflyers")(lambda c, m: listflyers_handler(c, m)))
    app.add_handler(filters.command("scheduleflyer")(lambda c, m: scheduleflyer_handler(c, m)))
    app.add_handler(filters.command("cancelflyer")(lambda c, m: cancelflyer_handler(c, m)))

