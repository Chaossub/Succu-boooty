import os
import logging
import json
from datetime import datetime
from pymongo import MongoClient
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters, types
from pyrogram.handlers import MessageHandler

# Set timezone
SCHED_TZ = "America/Los_Angeles"

# Setup logging
logger = logging.getLogger(__name__)

# Mongo setup
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME")

if not isinstance(MONGO_DB, str) or not MONGO_DB:
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DBNAME environment variable.")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyer_col = db["flyers"]

# Helper
def is_admin(user, chat):
    return user.id in [admin.user.id for admin in chat.get_members() if admin.status in ("administrator", "creator")]

# Register
def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: types.Message):
        if not message.photo:
            return await message.reply("❌ Please attach an image.")
        if not is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can use this.")

        try:
            _, name, caption = message.text.split(" ", 2)
        except:
            return await message.reply("Usage: /addflyer <name> <caption>")

        flyer_col.update_one(
            {"chat_id": message.chat.id, "name": name},
            {
                "$set": {
                    "file_id": message.photo.file_id,
                    "caption": caption
                }
            },
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' added.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def send_flyer(client, message: types.Message):
        try:
            _, name = message.text.split(maxsplit=1)
        except:
            return await message.reply("Usage: /flyer <name>")

        flyer = flyer_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: types.Message):
        flyers = flyer_col.find({"chat_id": message.chat.id})
        names = [f['name'] for f in flyers]
        if not names:
            return await message.reply("No flyers saved.")
        await message.reply("📄 Saved Flyers:\n" + "\n".join(names))

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: types.Message):
        if not is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can schedule flyers.")
        try:
            _, name, time_str, target_group = message.text.split(maxsplit=3)
        except:
            return await message.reply("Usage: /scheduleflyer <name> <HH:MM> <target_chat_id>")

        flyer = flyer_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(timezone(SCHED_TZ))
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time = run_time.replace(day=now.day + 1)

        job_id = f"{message.chat.id}_{name}_{target_group}"

        def send_scheduled_flyer():
            try:
                client.send_photo(
                    int(target_group),
                    flyer["file_id"],
                    caption=flyer["caption"]
                )
                logging.info(f"Scheduled flyer '{name}' sent to {target_group}")
            except Exception as e:
                logging.error(f"Error sending flyer: {e}")

        scheduler.add_job(
            send_scheduled_flyer,
            trigger="date",
            run_date=run_time,
            id=job_id,
            timezone=SCHED_TZ
        )
        await message.reply(f"✅ Scheduled flyer '{name}' to post in {target_group} at {run_time.strftime('%H:%M %Z')}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: types.Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("📭 No flyers scheduled.")
        lines = [f"{j.id} at {j.next_run_time.astimezone(timezone(SCHED_TZ)).strftime('%Y-%m-%d %H:%M %Z')}" for j in jobs]
        await message.reply("📅 Scheduled Flyers:\n" + "\n".join(lines))
