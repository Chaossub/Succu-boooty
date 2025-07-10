import os
import logging
import json
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from pymongo import MongoClient
from pytz import timezone

# ─── Logging ────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Environment Variables ──────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")
if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DB environment variable.")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_col = db.flyers
scheduled_col = db.scheduled_flyers

SCHED_TZ = os.getenv("SCHEDULER_TZ", "UTC")
TZ = timezone(SCHED_TZ)

# ─── Helpers ────────────────────────────────────────────────────────────────
async def is_admin(user, chat):
    async for member in chat.get_members():
        if member.status in ("administrator", "creator") and member.user.id == user.id:
            return True
    return False

def parse_time(time_str):
    try:
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(TZ)
        return TZ.localize(datetime(now.year, now.month, now.day, hour, minute))
    except Exception as e:
        return None

# ─── Commands ───────────────────────────────────────────────────────────────
def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not message.photo:
            await message.reply("Please attach a photo when using /addflyer <name> <caption>")
            return

        if not await is_admin(message.from_user, message.chat):
            await message.reply("Only admins can add flyers.")
            return

        parts = message.text.split(None, 2)
        if len(parts) < 3:
            await message.reply("Usage: /addflyer <name> <caption>")
            return
        name, caption = parts[1], parts[2]

        flyers_col.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {
                "chat_id": message.chat.id,
                "name": name,
                "caption": caption,
                "file_id": message.photo.file_id
            }},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) != 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = parts[1]
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if flyer:
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            await message.reply("Only admins can change flyers.")
            return

        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("Reply to the new photo with /changeflyer <name>")
            return

        parts = message.text.split(None, 1)
        if len(parts) != 2:
            await message.reply("Usage: /changeflyer <name>")
            return

        name = parts[1]
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            await message.reply("❌ Flyer not found.")
            return

        flyers_col.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.reply_to_message.photo.file_id}}
        )
        await message.reply(f"✅ Flyer '{name}' updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            await message.reply("Only admins can delete flyers.")
            return

        parts = message.text.split(None, 1)
        if len(parts) != 2:
            await message.reply("Usage: /deleteflyer <name>")
            return

        name = parts[1]
        result = flyers_col.delete_one({"chat_id": message.chat.id, "name": name})
        if result.deleted_count:
            await message.reply(f"✅ Flyer '{name}' deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyers_col.find({"chat_id": message.chat.id})
        flyer_names = [f"• {f['name']}" for f in flyers]
        if flyer_names:
            await message.reply("📋 Flyers:\n" + "\n".join(flyer_names))
        else:
            await message.reply("No flyers saved.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            await message.reply("Only admins can schedule flyers.")
            return

        parts = message.text.split(None, 3)
        if len(parts) < 4:
            await message.reply("Usage: /scheduleflyer <name> <HH:MM> <target_chat_id>")
            return

        name, time_str, target_chat_id = parts[1], parts[2], int(parts[3])
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            await message.reply("❌ Flyer not found.")
            return

        scheduled_time = parse_time(time_str)
        if not scheduled_time:
            await message.reply("Invalid time format. Use HH:MM (24hr).")
            return

        job_id = f"{message.chat.id}_{name}_{target_chat_id}_{scheduled_time.timestamp()}"
        scheduler.add_job(
            send_flyer_job,
            "date",
            run_date=scheduled_time,
            args=[client, flyer["file_id"], flyer["caption"], target_chat_id],
            id=job_id
        )
        scheduled_col.insert_one({
            "job_id": job_id,
            "file_id": flyer["file_id"],
            "caption": flyer["caption"],
            "target_chat_id": target_chat_id,
            "scheduled_time": scheduled_time.isoformat()
        })
        await message.reply(f"🗓️ Flyer '{name}' scheduled for {time_str} to be posted in {target_chat_id}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduled_col.find({"target_chat_id": message.chat.id})
        job_texts = []
        for j in jobs:
            job_texts.append(f"• Scheduled at {j['scheduled_time']}")
        if job_texts:
            await message.reply("⏰ Scheduled Flyers:\n" + "\n".join(job_texts))
        else:
            await message.reply("No flyers scheduled for this group.")

# ─── Job Function ───────────────────────────────────────────────────────────
async def send_flyer_job(client, file_id, caption, chat_id):
    try:
        await client.send_photo(chat_id, file_id, caption=caption)
    except Exception as e:
        logger.error(f"❌ Failed to send scheduled flyer: {e}")
