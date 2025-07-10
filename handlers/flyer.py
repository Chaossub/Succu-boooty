import os
import json
from datetime import datetime
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler

from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

FLYER_DIR = "flyers"
SCHEDULE_FILE = "scheduled_flyers.json"

if not os.path.exists(FLYER_DIR):
    os.makedirs(FLYER_DIR)

def flyer_file(chat_id):
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id=None):
    if chat_id:
        path = flyer_file(chat_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    return {}

def save_flyers(chat_id, flyers):
    with open(flyer_file(chat_id), "w") as f:
        json.dump(flyers, f, indent=2)

def load_scheduled():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    return []

def save_scheduled(data):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ───── Flyer Management ─────

@Client.on_message(filters.command("addflyer") & filters.photo)
async def add_flyer_with_photo(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can create flyers.")
        return
    if not message.caption or len(message.caption.split()) < 2:
        await message.reply("❌ Usage: Send photo with `/addflyer <name>` in caption.")
        return

    name = message.caption.split(None, 1)[1].strip()
    flyers = load_flyers(message.chat.id)
    if name in flyers:
        await message.reply("❌ Flyer with that name already exists.")
        return
    flyers[name] = {"file_id": message.photo.file_id, "caption": name}
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' added.")

@Client.on_message(filters.command("changeflyer") & filters.photo)
async def change_flyer_with_photo(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can change flyers.")
        return
    if not message.caption or len(message.caption.split()) < 2:
        await message.reply("❌ Usage: Send photo with `/changeflyer <name>` in caption.")
        return

    name = message.caption.split(None, 1)[1].strip()
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        await message.reply("❌ No flyer found with that name.")
        return
    flyers[name]["file_id"] = message.photo.file_id
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' image updated.")

@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /flyer <name>")
        return
    name = message.command[1]
    flyers = load_flyers(message.chat.id)
    flyer = flyers.get(name)
    if not flyer:
        await message.reply("❌ Flyer not found.")
        return
    await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])

@Client.on_message(filters.command("listflyers"))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers(message.chat.id)
    if not flyers:
        await message.reply("❌ No flyers found.")
        return
    text = "<b>📌 Flyers in this group:</b>\n\n" + "\n".join(f"• <code>{name}</code>" for name in flyers)
    await message.reply(text)

@Client.on_message(filters.command("deleteflyer"))
async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can delete flyers.")
        return
    if len(message.command) < 2:
        await message.reply("❌ Usage: /deleteflyer <name>")
        return
    name = message.command[1]
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        await message.reply("❌ Flyer not found.")
        return
    del flyers[name]
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' deleted.")

# ───── Scheduling ─────

@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can schedule flyers.")
        return
    if len(message.command) < 4:
        await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <group_id>")
        return
    name, time_str, chat_id = message.command[1], message.command[2], int(message.command[3])
    try:
        hour, minute = map(int, time_str.split(":"))
    except:
        await message.reply("❌ Invalid time format. Use HH:MM.")
        return
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        await message.reply("❌ Flyer not found.")
        return
    job = {
        "type": "flyer",
        "name": name,
        "chat_id": chat_id,
        "time": time_str
    }
    data = load_scheduled()
    data.append(job)
    save_scheduled(data)
    await message.reply(f"✅ Scheduled flyer '{name}' for {time_str}.")

@Client.on_message(filters.command("scheduletext"))
async def schedule_text(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can schedule text posts.")
        return
    if len(message.command) < 4:
        await message.reply("❌ Usage: /scheduletext <HH:MM> <group_id> <text>")
        return
    time_str, chat_id = message.command[1], int(message.command[2])
    text = " ".join(message.command[3:])
    try:
        hour, minute = map(int, time_str.split(":"))
    except:
        await message.reply("❌ Invalid time format. Use HH:MM.")
        return
    job = {
        "type": "text",
        "chat_id": chat_id,
        "time": time_str,
        "text": text
    }
    data = load_scheduled()
    data.append(job)
    save_scheduled(data)
    await message.reply(f"✅ Scheduled text post for {time_str}.")

@Client.on_message(filters.command("listscheduled"))
async def list_scheduled(client: Client, message: Message):
    data = load_scheduled()
    if not data:
        await message.reply("❌ No scheduled posts.")
        return
    text = "<b>⏰ Scheduled Posts:</b>\n\n"
    for i, job in enumerate(data):
        if job["type"] == "flyer":
            text += f"{i+1}. Flyer '{job['name']}' at {job['time']} to {job['chat_id']}\n"
        else:
            text += f"{i+1}. Text at {job['time']} to {job['chat_id']}\n"
    await message.reply(text)

@Client.on_message(filters.command("cancelflyer"))
async def cancel_flyer(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /cancelflyer <index>")
        return
    try:
        index = int(message.command[1]) - 1
    except:
        await message.reply("❌ Invalid index.")
        return
    data = load_scheduled()
    if index < 0 or index >= len(data):
        await message.reply("❌ Invalid index.")
        return
    job = data.pop(index)
    save_scheduled(data)
    await message.reply(f"✅ Canceled scheduled post: {job}")

async def send_scheduled_flyer(client: Client, job):
    flyers = load_flyers()
    flyer = flyers.get(job["name"])
    if flyer:
        await client.send_photo(job["chat_id"], flyer["file_id"], caption=flyer["caption"])

async def send_scheduled_text(client: Client, job):
    await client.send_message(job["chat_id"], job["text"])

def schedule_jobs(scheduler: BackgroundScheduler, client: Client):
    data = load_scheduled()
    for job in data:
        hour, minute = map(int, job["time"].split(":"))
        trigger = {"trigger": "cron", "hour": hour, "minute": minute, "timezone": timezone("US/Pacific")}
        if job["type"] == "flyer":
            scheduler.add_job(send_scheduled_flyer, **trigger, args=[client, job])
        elif job["type"] == "text":
            scheduler.add_job(send_scheduled_text, **trigger, args=[client, job])

def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(add_flyer_with_photo)
    app.add_handler(change_flyer_with_photo)
    app.add_handler(send_flyer)
    app.add_handler(list_flyers)
    app.add_handler(delete_flyer)
    app.add_handler(schedule_flyer)
    app.add_handler(schedule_text)
    app.add_handler(list_scheduled)
    app.add_handler(cancel_flyer)
    schedule_jobs(scheduler, app)

