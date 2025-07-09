import os
import json
import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── MongoDB Setup ───────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_collection = db["flyers"]
schedule_collection = db["flyer_schedule"]

# ─── Flyer Commands ───────────────────────────────────────────────────────────
async def add_flyer(client: Client, message: Message):
    if not message.photo:
        return await message.reply_text("📸 Please attach an image when adding a flyer.")
    if not message.text:
        return await message.reply_text("Usage: /addflyer <name> <caption>")
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.reply_text("Usage: /addflyer <name> <caption>")
    name, caption = parts[1], parts[2]

    flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
    if flyer:
        return await message.reply_text("⚠️ A flyer with that name already exists.")

    file_id = message.photo.file_id
    flyers_collection.insert_one({
        "chat_id": message.chat.id,
        "name": name,
        "file_id": file_id,
        "caption": caption
    })
    await message.reply_text(f"✅ Flyer '{name}' added successfully.")

async def get_flyer(client: Client, message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /flyer <name>")
    name = parts[1]
    flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply_text("❌ Flyer not found.")
    await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

async def change_flyer(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("📸 Reply to the new flyer image with /changeflyer <name>.")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /changeflyer <name>")
    name = parts[1]
    new_file_id = message.reply_to_message.photo.file_id
    result = flyers_collection.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": new_file_id}}
    )
    if result.modified_count:
        await message.reply_text(f"🔁 Flyer '{name}' updated with new image.")
    else:
        await message.reply_text("❌ Flyer not found.")

async def delete_flyer(client: Client, message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /deleteflyer <name>")
    name = parts[1]
    result = flyers_collection.delete_one({"chat_id": message.chat.id, "name": name})
    if result.deleted_count:
        await message.reply_text(f"🗑️ Flyer '{name}' deleted.")
    else:
        await message.reply_text("❌ Flyer not found.")

async def list_flyers(client: Client, message: Message):
    flyers = list(flyers_collection.find({"chat_id": message.chat.id}))
    if not flyers:
        return await message.reply_text("📭 No flyers found.")
    text = "📌 Flyers:\n" + "\n".join([f"• {f['name']}" for f in flyers])
    await message.reply_text(text)

# ─── Scheduling ───────────────────────────────────────────────────────────────
def post_flyer_job(app: Client, chat_id: int, name: str):
    flyer = flyers_collection.find_one({"chat_id": chat_id, "name": name})
    if flyer:
        app.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])

def schedule_flyer_post(scheduler, app: Client, chat_id: int, name: str, post_time: str):
    dt = datetime.fromisoformat(post_time)
    scheduler.add_job(post_flyer_job, 'date', run_date=dt, args=[app, chat_id, name])
    schedule_collection.insert_one({"chat_id": chat_id, "name": name, "post_time": post_time})

async def schedule_flyer(client: Client, message: Message):
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.reply_text("Usage: /scheduleflyer <name> <YYYY-MM-DDTHH:MM>")
    name, post_time = parts[1], parts[2]
    try:
        datetime.fromisoformat(post_time)
    except ValueError:
        return await message.reply_text("❌ Invalid datetime format. Use YYYY-MM-DDTHH:MM")
    schedule_flyer_post(client.scheduler, client, message.chat.id, name, post_time)
    await message.reply_text(f"📅 Scheduled flyer '{name}' for {post_time}.")

async def list_flyer_jobs(client: Client, message: Message):
    jobs = list(schedule_collection.find())
    if not jobs:
        return await message.reply_text("📭 No flyer jobs are currently scheduled.")
    lines = []
    for job in jobs:
        time = datetime.fromisoformat(job["post_time"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"📌 Flyer: <b>{job['name']}</b>\n📤 Group: <code>{job['chat_id']}</code>\n🕓 Time: {time}\n")
    await message.reply_text("\n".join(lines), parse_mode="HTML")

# ─── Register ────────────────────────────────────────────────────────────────
def register(app: Client):
    app.add_handler(filters.command("addflyer") & filters.group)(add_flyer)
    app.add_handler(filters.command("flyer") & filters.group)(get_flyer)
    app.add_handler(filters.command("changeflyer") & filters.group)(change_flyer)
    app.add_handler(filters.command("deleteflyer") & filters.group)(delete_flyer)
    app.add_handler(filters.command("listflyers") & filters.group)(list_flyers)
    app.add_handler(filters.command("scheduleflyer") & filters.group)(schedule_flyer)
    app.add_handler(filters.command("listflyerjobs") & filters.group)(list_flyer_jobs)
