import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Logging
logger = logging.getLogger(__name__)

# MongoDB Setup
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DB environment variable.")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers = db.flyers
schedules = db.scheduled_flyers

def is_admin(user, chat):
    return user and user.id in [admin.user.id async for admin in chat.get_members() if admin.status in ("administrator", "creator")]

def schedule_post(scheduler, client, group_id, flyer):
    def post():
        media = flyer["file_id"]
        caption = flyer["caption"]
        try:
            client.send_photo(group_id, media, caption=caption)
        except Exception as e:
            logger.error(f"Failed to send scheduled flyer: {e}")

    job_id = f"{group_id}_{flyer['name']}"
    return scheduler.add_job(post, trigger="cron", id=job_id, day_of_week=flyer["day"], hour=flyer["hour"], minute=flyer["minute"])

def register(app, scheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("❌ You must be an admin to use this.")

        if not message.photo:
            return await message.reply("❌ Please send an image with the command.")

        parts = message.text.split(None, 2)
        if len(parts) < 3:
            return await message.reply("Usage: /addflyer <name> <caption>")

        name = parts[1].lower()
        caption = parts[2]

        flyers.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.photo.file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' added.")

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("❌ You must be an admin to use this.")
        if not message.reply_to_message.photo:
            return await message.reply("❌ Please reply to a photo.")

        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("Usage: /changeflyer <name>")

        name = parts[1].lower()

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        flyers.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.reply_to_message.photo.file_id}},
        )
        await message.reply(f"✅ Flyer '{name}' image updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("❌ You must be an admin to use this.")

        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("Usage: /deleteflyer <name>")

        name = parts[1].lower()

        flyers.delete_one({"chat_id": message.chat.id, "name": name})
        await message.reply(f"🗑️ Flyer '{name}' deleted.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        results = flyers.find({"chat_id": message.chat.id})
        names = [flyer["name"] for flyer in results]
        if not names:
            await message.reply("📭 No flyers found.")
        else:
            await message.reply("📌 Flyers:\n" + "\n".join(f"- {name}" for name in names))

    @app.on_message(filters.command("flyer") & filters.group)
    async def send_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("Usage: /flyer <name>")

        name = parts[1].lower()
        flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer_cmd(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("❌ You must be an admin to use this.")

        parts = message.text.split(None, 3)
        if len(parts) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <day> <HH:MM>")

        name, day, time_str = parts[1].lower(), parts[2].lower(), parts[3]
        hour, minute = map(int, time_str.split(":"))

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        flyer.update({"day": day, "hour": hour, "minute": minute, "name": name})
        flyer["chat_id"] = message.chat.id
        schedules.update_one({"chat_id": message.chat.id, "name": name}, {"$set": flyer}, upsert=True)

        job_id = f"{message.chat.id}_{name}"
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        schedule_post(scheduler, client, message.chat.id, flyer)
        await message.reply(f"✅ Scheduled '{name}' for {day} at {time_str}")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("📭 No scheduled flyer jobs.")
        job_list = "\n".join([f"🕒 {job.id} — {job.trigger}" for job in jobs])
        await message.reply(f"📅 Scheduled Jobs:\n{job_list}")
