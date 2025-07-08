import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# ── Configuration ────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI environment variable")

MONGO_DB = os.getenv("MONGO_DB", "chaossunflowerbusiness321")

# ── Database Setup ────────────────────────────────────────────────────────────
mongo_client = MongoClient(MONGO_URI)
db           = mongo_client[MONGO_DB]
flyers_col   = db.flyers

# ── Scheduler Setup ──────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()

async def _send_flyer(app, flyer: dict):
    """Internal: sends the flyer (photo+caption or just text)."""
    chat_id = flyer["chat_id"]
    text    = flyer["text"]
    if flyer.get("photo"):
        await app.send_photo(chat_id, flyer["photo"], caption=text)
    else:
        await app.send_message(chat_id, text)

def register(app):
    # Start scheduler so scheduled jobs can run
    scheduler.start()

    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer(_, message: Message):
        parts = message.text.split(None, 2)
        if len(parts) < 3:
            return await message.reply_text("Usage: /addflyer <name> <text>")
        name, text = parts[1], parts[2]
        photo = None
        if message.reply_to_message and message.reply_to_message.photo:
            photo = message.reply_to_message.photo.file_id
        flyers_col.insert_one({
            "chat_id": message.chat.id,
            "name":    name,
            "text":    text,
            "photo":   photo
        })
        await message.reply_text(f"✅ Flyer **{name}** added.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers(_, message: Message):
        docs = flyers_col.find({"chat_id": message.chat.id})
        names = [d["name"] for d in docs]
        if not names:
            return await message.reply_text("No flyers found in this chat.")
        await message.reply_text("📜 Available flyers:\n" + "\n".join(names))

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer(_, message: Message):
        parts = message.text.split(None, 3)
        if len(parts) != 4:
            return await message.reply_text("Usage: /scheduleflyer <name> YYYY-MM-DD HH:MM")
        name, date_str, time_str = parts[1], parts[2], parts[3]
        try:
            run_dt = datetime.fromisoformat(f"{date_str} {time_str}")
        except ValueError:
            return await message.reply_text("❌ Invalid date/time. Use `YYYY-MM-DD HH:MM`")
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply_text(f"❌ No flyer named **{name}** found.")
        job_id = f"{message.chat.id}-{name}-{int(run_dt.timestamp())}"
        scheduler.add_job(
            _send_flyer,
            "date",
            run_date=run_dt,
            args=[app, flyer],
            id=job_id
        )
        await message.reply_text(f"⏰ Scheduled **{name}** at {run_dt} (job `{job_id}`).")

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancelflyer(_, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) != 2:
            return await message.reply_text("Usage: /cancelflyer <job_id>")
        job_id = parts[1]
        try:
            scheduler.remove_job(job_id)
            await message.reply_text(f"🗑️ Canceled job `{job_id}`.")
        except Exception:
            await message.reply_text(f"❌ No scheduled job with ID `{job_id}`.")
