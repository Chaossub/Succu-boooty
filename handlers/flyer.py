import os
import logging
import asyncio
from datetime import datetime, timedelta
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message, InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Owner/Admin ---
OWNER_ID = 6964994611

# --- Group aliases from env ---
ALIASES = {
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT", "0")),
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY", "0")),
    "TEST_GROUP": int(os.getenv("TEST_GROUP", "0")),
}
ALIASES_INV = {v: k for k, v in ALIASES.items()}

# --- Mongo ---
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers = mongo.flyers

def group_name_to_id(name):
    name = name.upper()
    if name in ALIASES:
        return ALIASES[name]
    try:
        gid = int(name)
        if gid in ALIASES.values():
            return gid
    except Exception:
        pass
    raise ValueError("Invalid group/alias.")

def is_owner(func):
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.from_user.id != OWNER_ID:
            return await message.reply("❌ Only the owner can do this.")
        return await func(client, message, *args, **kwargs)
    return wrapper

def register(app, scheduler: BackgroundScheduler):
    logger.info("📢 flyer.register() called")

    # Add a text or photo flyer
    @app.on_message(filters.command("addflyer") & filters.group)
    @is_owner
    async def addflyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption> (optional, send with photo or just text)")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:]) if len(message.command) > 2 else ""
        if flyers.find_one({"name": name}):
            return await message.reply("❌ Flyer already exists.")

        if message.photo:
            photo_id = message.photo.file_id
            flyers.insert_one({
                "name": name,
                "caption": caption,
                "type": "photo",
                "photo_id": photo_id,
            })
            await message.reply(f"✅ Photo flyer '{name}' added.")
        else:
            flyers.insert_one({
                "name": name,
                "caption": caption,
                "type": "text"
            })
            await message.reply(f"✅ Text flyer '{name}' added.")

    # Change an existing flyer (must reply to photo)
    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    @is_owner
    async def changeflyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> (must reply to new photo)")
        name = message.command[1].lower()
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if not message.reply_to_message.photo:
            return await message.reply("❌ Reply to a photo to update flyer image.")
        photo_id = message.reply_to_message.photo.file_id
        flyers.update_one({"name": name}, {"$set": {"photo_id": photo_id, "type": "photo"}})
        await message.reply(f"✅ Flyer '{name}' image updated.")

    # Delete a flyer
    @app.on_message(filters.command("deleteflyer") & filters.group)
    @is_owner
    async def deleteflyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = message.command[1].lower()
        flyers.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # List all flyers
    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message: Message):
        all_flyers = list(flyers.find({}))
        if not all_flyers:
            return await message.reply("No flyers.")
        text = "\n".join([f"- {f['name']} ({f['type']})" for f in all_flyers])
        await message.reply(f"<b>Flyers:</b>\n{text}")

    # Retrieve a flyer
    @app.on_message(filters.command("flyer"))
    async def getflyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = message.command[1].lower()
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer["type"] == "photo":
            await message.reply_photo(flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

    # --- Scheduled Flyers ---
    def run_async_job(coro):
        # Schedules must be run in main thread event loop
        loop = asyncio.get_event_loop()
        loop.create_task(coro)

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    @is_owner
    async def scheduleflyer(client, message: Message):
        """ /scheduleflyer <name> <HH:MM> <group> <once/daily> """
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <group> <once|daily>")
        name, timestr, group, freq = args[1].lower(), args[2], args[3].upper(), args[4].lower()
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        try:
            group_id = group_name_to_id(group)
        except Exception:
            return await message.reply("❌ Invalid group/alias.")

        now = datetime.now()
        hour, minute = map(int, timestr.split(":"))
        send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if send_time < now:
            send_time += timedelta(days=1)

        def flyer_job():
            async def do_post():
                try:
                    logger.info(f"Trying to post flyer '{name}' to {group_id} ({type(group_id)})")
                    if flyer["type"] == "photo":
                        await app.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
                    else:
                        await app.send_message(group_id, flyer.get("caption", ""))
                except Exception as e:
                    logger.error(f"Failed to post flyer: {e}")

            asyncio.run(do_post())

        job_id = f"flyer_{name}_{group_id}_{int(send_time.timestamp())}"

        if freq == "once":
            scheduler.add_job(flyer_job, 'date', run_date=send_time, id=job_id)
        elif freq == "daily":
            scheduler.add_job(flyer_job, 'cron', hour=hour, minute=minute, id=job_id)
        else:
            return await message.reply("❌ Freq must be once or daily")

        await message.reply(
            f"✅ Scheduled flyer '{name}' to {group} at {timestr} ({freq}).\n"
            f"Job ID: <code>{job_id}</code>"
        )

    @app.on_message(filters.command("scheduletext") & filters.group)
    @is_owner
    async def scheduletext(client, message: Message):
        """ /scheduletext <HH:MM> <group> <once|daily> <text> """
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <group> <once|daily> <text>")
        timestr, group, freq, text = args[1], args[2].upper(), args[3].lower(), args[4]

        try:
            group_id = group_name_to_id(group)
        except Exception:
            return await message.reply("❌ Invalid group/alias.")

        now = datetime.now()
        hour, minute = map(int, timestr.split(":"))
        send_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if send_time < now:
            send_time += timedelta(days=1)

        def text_job():
            async def do_post():
                try:
                    await app.send_message(group_id, text)
                except Exception as e:
                    logger.error(f"Failed to post scheduled text: {e}")
            asyncio.run(do_post())

        job_id = f"text_{group_id}_{int(send_time.timestamp())}"

        if freq == "once":
            scheduler.add_job(text_job, 'date', run_date=send_time, id=job_id)
        elif freq == "daily":
            scheduler.add_job(text_job, 'cron', hour=hour, minute=minute, id=job_id)
        else:
            return await message.reply("❌ Freq must be once or daily")

        await message.reply(
            f"✅ Scheduled text to {group} at {timestr} ({freq}).\n"
            f"Job ID: <code>{job_id}</code>"
        )

    @app.on_message(filters.command("listscheduled"))
    async def listscheduled(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No flyers scheduled.")
        lines = []
        for j in jobs:
            lines.append(
                f"- {j.id} [{j.next_run_time}]"
            )
        await message.reply("<b>Scheduled Flyers:</b>\n" + "\n".join(lines))

    @app.on_message(filters.command("cancelflyer"))
    @is_owner
    async def cancelflyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = message.command[1]
        job = scheduler.get_job(job_id)
        if job:
            scheduler.remove_job(job_id)
            await message.reply(f"✅ Cancelled job {job_id}")
        else:
            await message.reply("❌ Job not found.")
