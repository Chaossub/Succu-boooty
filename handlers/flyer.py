import os
import json
from datetime import datetime, timedelta
from pyrogram import filters
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

from pymongo import MongoClient
from pyrogram.client import Client

# ─── MongoDB Setup ─────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB") or os.environ.get("MONGO_DB_NAME")

if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DB environment variable.")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_col = db["flyers"]

# ─── Helper Functions ──────────────────────────────────────────────────────────
def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

def parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        return None

# ─── Commands ──────────────────────────────────────────────────────────────────
async def add_flyer(client, message: Message):
    if not message.photo:
        return await message.reply("Please attach a photo with this command.")

    if not is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can add flyers.")

    try:
        _, name, caption = message.text.split(None, 2)
    except Exception:
        return await message.reply("Usage:\n<code>/addflyer &lt;name&gt; &lt;caption&gt;</code> with a photo")

    file_id = message.photo.file_id
    flyers_col.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"caption": caption, "file_id": file_id}},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{name}</b> added successfully.")

async def flyer(client, message: Message):
    if not is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can use this command.")
    if len(message.command) < 2:
        return await message.reply("Usage: /flyer <name>")

    name = message.command[1]
    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    await client.send_photo(
        chat_id=message.chat.id,
        photo=flyer["file_id"],
        caption=flyer["caption"]
    )

async def change_flyer(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to a photo to change a flyer.")

    if not is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can change flyers.")

    if len(message.command) < 2:
        return await message.reply("Usage: /changeflyer <name>")

    name = message.command[1]
    file_id = message.reply_to_message.photo.file_id
    updated = flyers_col.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"file_id": file_id}}
    )

    if updated.matched_count == 0:
        await message.reply("❌ Flyer not found.")
    else:
        await message.reply(f"✅ Flyer <b>{name}</b> image updated.")

async def delete_flyer(client, message: Message):
    if not is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can delete flyers.")

    if len(message.command) < 2:
        return await message.reply("Usage: /deleteflyer <name>")

    name = message.command[1]
    result = flyers_col.delete_one({"chat_id": message.chat.id, "name": name})
    if result.deleted_count == 0:
        await message.reply("❌ Flyer not found.")
    else:
        await message.reply(f"🗑️ Flyer <b>{name}</b> deleted.")

async def list_flyers(client, message: Message):
    flyers = flyers_col.find({"chat_id": message.chat.id})
    names = [f["name"] for f in flyers]
    if not names:
        await message.reply("No flyers found.")
    else:
        text = "📌 Flyers:\n" + "\n".join(f"• {name}" for name in names)
        await message.reply(text)

async def schedule_flyer(client, message: Message, scheduler: BackgroundScheduler):
    if not is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only admins can schedule flyers.")

    try:
        _, name, time_str, target_chat_id = message.text.split(None, 3)
        target_chat_id = int(target_chat_id)
    except:
        return await message.reply("Usage:\n<code>/scheduleflyer &lt;name&gt; &lt;HH:MM&gt; &lt;target_chat_id&gt;</code>")

    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    post_time = parse_time(time_str)
    if not post_time:
        return await message.reply("❌ Invalid time format. Use HH:MM in 24hr format.")

    trigger = CronTrigger(hour=post_time.hour, minute=post_time.minute, timezone="America/Los_Angeles")

    def send_job():
        client.send_photo(chat_id=target_chat_id, photo=flyer["file_id"], caption=flyer["caption"])

    scheduler.add_job(send_job, trigger=trigger)
    await message.reply(f"✅ Scheduled flyer <b>{name}</b> for {time_str} to <code>{target_chat_id}</code>.")

async def list_jobs(client, message: Message, scheduler: BackgroundScheduler):
    jobs = scheduler.get_jobs()
    if not jobs:
        await message.reply("No jobs scheduled.")
        return
    text = "📆 Scheduled Jobs:\n"
    for job in jobs:
        text += f"• {job.name} — next: {job.next_run_time}\n"
    await message.reply(text)

# ─── Register ──────────────────────────────────────────────────────────────────
def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(filters.command("addflyer") & filters.photo, add_flyer)
    app.add_handler(filters.command("flyer"), flyer)
    app.add_handler(filters.command("changeflyer"), change_flyer)
    app.add_handler(filters.command("deleteflyer"), delete_flyer)
    app.add_handler(filters.command("listflyers"), list_flyers)
    app.add_handler(filters.command("scheduleflyer"), lambda c, m: schedule_flyer(c, m, scheduler))
    app.add_handler(filters.command("listjobs"), lambda c, m: list_jobs(c, m, scheduler))
