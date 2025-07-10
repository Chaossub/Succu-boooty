import os
import json
import logging
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

from pyrogram.handlers import MessageHandler

# Logging
logger = logging.getLogger(__name__)

# Mongo Setup
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")

if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DB environment variable.")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_collection = db["flyers"]
schedule_collection = db["scheduled_flyers"]

# Scheduler
scheduler = BackgroundScheduler(timezone=os.environ.get("SCHED_TZ", "UTC"))
scheduler.start()


async def is_admin(user, chat):
    async for member in chat.iter_members():
        if member.user.id == user.id and member.status in ("administrator", "creator"):
            return True
    return False


async def add_flyer(client, message: Message):
    if not await is_admin(message.from_user, message.chat):
        await message.reply("Only admins can use this command.")
        return

    if not message.photo or not message.caption:
        await message.reply("Please send an image with a caption to use /addflyer <name> <caption>.")
        return

    parts = message.caption.split(None, 2)
    if len(parts) < 3:
        await message.reply("Usage: /addflyer <name> <caption>")
        return

    _, name, caption = parts
    file_id = message.photo.file_id
    flyers_collection.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": file_id, "caption": caption}},
        upsert=True,
    )
    await message.reply(f"✅ Flyer '{name}' saved.")


async def change_flyer(client, message: Message):
    if not await is_admin(message.from_user, message.chat):
        await message.reply("Only admins can use this command.")
        return

    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.reply("Please reply to a photo to use this command.")
        return

    parts = message.text.split(None, 1)
    if len(parts) < 2:
        await message.reply("Usage: /changeflyer <name>")
        return

    name = parts[1]
    file_id = message.reply_to_message.photo.file_id

    flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        await message.reply("Flyer not found.")
        return

    flyers_collection.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": file_id}},
    )
    await message.reply(f"✅ Flyer '{name}' updated.")


async def delete_flyer(client, message: Message):
    if not await is_admin(message.from_user, message.chat):
        await message.reply("Only admins can use this command.")
        return

    parts = message.text.split(None, 1)
    if len(parts) < 2:
        await message.reply("Usage: /deleteflyer <name>")
        return

    name = parts[1]
    flyers_collection.delete_one({"chat_id": message.chat.id, "name": name})
    await message.reply(f"🗑️ Flyer '{name}' deleted.")


async def list_flyers(client, message: Message):
    flyers = flyers_collection.find({"chat_id": message.chat.id})
    names = [flyer["name"] for flyer in flyers]
    if names:
        await message.reply("📋 Flyers:\n" + "\n".join(f"• {n}" for n in names))
    else:
        await message.reply("No flyers found.")


async def send_flyer(client, message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        await message.reply("Usage: /flyer <name>")
        return

    name = parts[1]
    flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        await message.reply("Flyer not found.")
        return

    await message.reply_photo(flyer["file_id"], caption=flyer["caption"])


async def schedule_flyer(client, message: Message):
    if not await is_admin(message.from_user, message.chat):
        await message.reply("Only admins can use this command.")
        return

    parts = message.text.split(None, 3)
    if len(parts) < 4:
        await message.reply("Usage: /scheduleflyer <name> <YYYY-MM-DD> <HH:MM>")
        return

    _, name, date_str, time_str = parts
    flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        await message.reply("Flyer not found.")
        return

    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    job_id = f"{message.chat.id}_{name}_{dt.isoformat()}"

    async def send_scheduled_flyer():
        await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])
        schedule_collection.delete_one({"job_id": job_id})

    scheduler.add_job(send_scheduled_flyer, trigger="date", run_date=dt, id=job_id)
    schedule_collection.insert_one({
        "chat_id": message.chat.id,
        "name": name,
        "datetime": dt,
        "job_id": job_id,
    })

    await message.reply(f"⏰ Scheduled flyer '{name}' for {dt.strftime('%Y-%m-%d %H:%M')}.")


async def list_scheduled(client, message: Message):
    entries = schedule_collection.find({"chat_id": message.chat.id})
    lines = []
    for entry in entries:
        dt = entry["datetime"].strftime("%Y-%m-%d %H:%M")
        lines.append(f"• {entry['name']} at {dt}")
    if lines:
        await message.reply("📆 Scheduled Flyers:\n" + "\n".join(lines))
    else:
        await message.reply("No scheduled flyers.")


def register(app):
    app.add_handler(MessageHandler(add_flyer, filters.command("addflyer")))
    app.add_handler(MessageHandler(change_flyer, filters.command("changeflyer")))
    app.add_handler(MessageHandler(delete_flyer, filters.command("deleteflyer")))
    app.add_handler(MessageHandler(list_flyers, filters.command("listflyers")))
    app.add_handler(MessageHandler(send_flyer, filters.command("flyer")))
    app.add_handler(MessageHandler(schedule_flyer, filters.command("scheduleflyer")))
    app.add_handler(MessageHandler(list_scheduled, filters.command("listjobs")))
