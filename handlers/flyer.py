import os
import logging
from datetime import datetime
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters
from pyrogram.types import Message

# ─── Logging ──────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─── MongoDB setup ───────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable must be set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client.get_default_database()
flyers_col = db["flyers"]

# ─── Scheduler setup ─────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()
scheduler.start()

# ─── Database helper functions ───────────────────────────────────────────
def add_flyer_to_db(chat_id: int, name: str, text: str, image_file_id: str = None):
    flyers_col.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": {
            "text": text,
            "image_file_id": image_file_id,
            "updated_at": datetime.utcnow()
        }},
        upsert=True
    )

def get_flyer_from_db(chat_id: int, name: str):
    return flyers_col.find_one({"chat_id": chat_id, "name": name})

def list_flyers_in_db(chat_id: int):
    return list(flyers_col.find({"chat_id": chat_id}))

def remove_flyer_from_db(chat_id: int, name: str):
    flyers_col.delete_one({"chat_id": chat_id, "name": name})

# ─── Handler registration ─────────────────────────────────────────────────
def register(app):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_cmd(client, message: Message):
        """
        Usage:
          /addflyer <name> <text>
        Optionally attach a photo; its file_id will be stored too.
        """
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply_text("Usage: /addflyer <name> <text>")

        name, text = args[1], args[2]
        file_id = None
        if message.photo:
            file_id = message.photo.file_id

        add_flyer_to_db(message.chat.id, name, text, file_id)
        await message.reply_text(f"✅ Flyer **{name}** saved.", parse_mode="markdown")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_cmd(client, message: Message):
        flyers = list_flyers_in_db(message.chat.id)
        if not flyers:
            return await message.reply_text("No flyers found in this group.")
        lines = [f"- **{f['name']}**" for f in flyers]
        text = "📋 Flyers:\n" + "\n".join(lines)
        await message.reply_text(text, parse_mode="markdown")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_cmd(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply_text("Usage: /deleteflyer <name>")
        name = args[1]
        remove_flyer_from_db(message.chat.id, name)
        await message.reply_text(f"🗑 Flyer **{name}** deleted.", parse_mode="markdown")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_cmd(client, message: Message):
        """
        Usage: /scheduleflyer <name> YYYY-MM-DD HH:MM
        """
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            return await message.reply_text("Usage: /scheduleflyer <name> YYYY-MM-DD HH:MM")

        name, date_str, time_str = args[1], args[2], args[3]
        try:
            run_datetime = datetime.fromisoformat(f"{date_str}T{time_str}")
        except ValueError:
            return await message.reply_text("❌ Invalid datetime. Use YYYY-MM-DD HH:MM")

        flyer = get_flyer_from_db(message.chat.id, name)
        if not flyer:
            return await message.reply_text(f"❌ Flyer **{name}** not found.")

        chat_id = message.chat.id
        job_id = f"{chat_id}-{name}-{int(run_datetime.timestamp())}"

        def job(chat_id=chat_id, name=name):
            f = get_flyer_from_db(chat_id, name)
            if not f:
                return
            if f.get("image_file_id"):
                client.send_photo(chat_id, f["image_file_id"], caption=f["text"])
            else:
                client.send_message(chat_id, f["text"])

        scheduler.add_job(
            job,
            "date",
            run_date=run_datetime,
            id=job_id,
            replace_existing=True
        )

        await message.reply_text(
            f"⏰ Flyer **{name}** scheduled for {run_datetime.strftime('%Y-%m-%d %H:%M')}",
            parse_mode="markdown"
        )

    @app.on_message(filters.command("listjobs") & filters.group)
    async def listjobs_cmd(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply_text("No scheduled flyers.")
        lines = [
            f"- `{job.id}` at `{job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}`"
            for job in jobs
        ]
        text = "🗓 Scheduled jobs:\n" + "\n".join(lines)
        await message.reply_text(text, parse_mode="markdown")
