import os
import json
import logging
from datetime import datetime
from pytz import timezone

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]
flyers_col = db["flyers"]
schedules_col = db["scheduled_flyers"]

# Group shortcuts from env vars
GROUP_SHORTCUTS = {
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY", 0)),
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT", 0)),
    "TEST_GROUP": int(os.getenv("TEST_GROUP", 0)),
}

# Helper to check admin
async def is_admin(client, chat_id, user_id):
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")

# /addflyer <name> <caption>
async def add_flyer(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can create flyers.")
    if not message.photo or len(message.command) < 3:
        return await message.reply("Usage: /addflyer <name> <caption> (with attached photo)")
    name = message.command[1].lower()
    caption = " ".join(message.command[2:])
    flyers_col.replace_one(
        {"chat_id": message.chat.id, "name": name},
        {
            "chat_id": message.chat.id,
            "name": name,
            "caption": caption,
            "file_id": message.photo.file_id,
        },
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' saved.")

# /changeflyer <name> (reply to new photo)
async def change_flyer(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can change flyers.")
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to a photo to update the flyer image.")
    if len(message.command) < 2:
        return await message.reply("Usage: /changeflyer <name>")
    name = message.command[1].lower()
    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("Flyer not found.")
    flyers_col.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": message.reply_to_message.photo.file_id}}
    )
    await message.reply(f"✅ Flyer '{name}' image updated.")

# /deleteflyer <name>
async def delete_flyer(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can delete flyers.")
    if len(message.command) < 2:
        return await message.reply("Usage: /deleteflyer <name>")
    name = message.command[1].lower()
    flyers_col.delete_one({"chat_id": message.chat.id, "name": name})
    await message.reply(f"🗑️ Flyer '{name}' deleted.")

# /listflyers
async def list_flyers(client, message: Message):
    flyers = flyers_col.find({"chat_id": message.chat.id})
    names = [f"- <b>{f['name']}</b>" for f in flyers]
    if not names:
        return await message.reply("No flyers saved.")
    await message.reply("📂 Saved Flyers:\n" + "\n".join(names))

# /flyer <name>
async def get_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /flyer <name>")
    name = message.command[1].lower()
    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("Flyer not found.")
    await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])

# /scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <target_group>
async def schedule_flyer(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can schedule flyers.")
    if len(message.command) < 5:
        return await message.reply("Usage: /scheduleflyer <name> <date> <time> <target_group>")
    name = message.command[1].lower()
    date_str = message.command[2]
    time_str = message.command[3]
    group_key = message.command[4]
    target_chat_id = GROUP_SHORTCUTS.get(group_key.upper())
    if not target_chat_id:
        return await message.reply("Invalid group shortcut.")

    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("Flyer not found.")

    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    tz = timezone(os.getenv("SCHEDULER_TZ", "UTC"))
    dt = tz.localize(dt)

    job = scheduler.add_job(
        send_scheduled_flyer,
        "date",
        run_date=dt,
        args=[client, target_chat_id, flyer["file_id"], flyer["caption"]],
    )

    schedules_col.insert_one({
        "job_id": job.id,
        "chat_id": message.chat.id,
        "flyer": name,
        "target": target_chat_id,
        "datetime": dt.isoformat()
    })

    await message.reply(f"🗓️ Scheduled flyer '{name}' for {dt.strftime('%Y-%m-%d %H:%M %Z')} to group {group_key}.")

# /scheduletext <message> <YYYY-MM-DD> <HH:MM> <target_group>
async def schedule_text(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can schedule text posts.")
    try:
        split = message.text.split(maxsplit=4)
        _, text, date_str, time_str, group_key = split
    except ValueError:
        return await message.reply("Usage: /scheduletext <message> <date> <time> <target_group>")
    
    target_chat_id = GROUP_SHORTCUTS.get(group_key.upper())
    if not target_chat_id:
        return await message.reply("Invalid group shortcut.")

    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    tz = timezone(os.getenv("SCHEDULER_TZ", "UTC"))
    dt = tz.localize(dt)

    job = scheduler.add_job(
        send_text_post,
        "date",
        run_date=dt,
        args=[client, target_chat_id, text],
    )

    schedules_col.insert_one({
        "job_id": job.id,
        "chat_id": message.chat.id,
        "type": "text",
        "text": text,
        "target": target_chat_id,
        "datetime": dt.isoformat()
    })

    await message.reply(f"📝 Scheduled text post for {dt.strftime('%Y-%m-%d %H:%M %Z')}.")

# /listjobs
async def list_jobs(client, message: Message):
    jobs = list(schedules_col.find({"chat_id": message.chat.id}))
    if not jobs:
        return await message.reply("No scheduled posts.")
    reply = ""
    for j in jobs:
        dt = datetime.fromisoformat(j["datetime"]).strftime("%Y-%m-%d %H:%M")
        reply += f"📌 {j['flyer'] if 'flyer' in j else j['text'][:20]} → {dt} → ID: <code>{j['job_id']}</code>\n"
    await message.reply(reply)

# /canceljob <job_id>
async def cancel_job(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /canceljob <job_id>")
    job_id = message.command[1]
    scheduler.remove_job(job_id)
    schedules_col.delete_one({"job_id": job_id})
    await message.reply(f"❌ Job {job_id} cancelled.")

# Posting functions
async def send_scheduled_flyer(client, chat_id, file_id, caption):
    await client.send_photo(chat_id, file_id, caption=caption)

async def send_text_post(client, chat_id, text):
    await client.send_message(chat_id, text)

# Register
def register(app, scheduler: BackgroundScheduler):
    app.add_handler(MessageHandler(add_flyer, filters.command("addflyer")))
    app.add_handler(MessageHandler(change_flyer, filters.command("changeflyer")))
    app.add_handler(MessageHandler(delete_flyer, filters.command("deleteflyer")))
    app.add_handler(MessageHandler(list_flyers, filters.command("listflyers")))
    app.add_handler(MessageHandler(get_flyer, filters.command("flyer")))
    app.add_handler(MessageHandler(schedule_flyer, filters.command("scheduleflyer")))
    app.add_handler(MessageHandler(schedule_text, filters.command("scheduletext")))
    app.add_handler(MessageHandler(list_jobs, filters.command("listjobs")))
    app.add_handler(MessageHandler(cancel_job, filters.command("canceljob")))
