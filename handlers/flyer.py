import os
import json
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.check_admin import is_admin

FLYER_FILE = "data/flyers.json"
SCHEDULE_FILE = "data/scheduled_posts.json"

def load_flyers():
    if not os.path.exists(FLYER_FILE):
        return {}
    with open(FLYER_FILE, "r") as f:
        return json.load(f)

def save_flyers(flyers):
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=2)

def load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    with open(SCHEDULE_FILE, "r") as f:
        return json.load(f)

def save_schedule(schedule):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

# ─────────────── Flyer Commands ───────────────────

@Client.on_message(filters.command("addflyer"))
async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can create flyers.")
    if not message.photo:
        return await message.reply("Please send an image with this command.")
    if len(message.command) < 2:
        return await message.reply("Usage: /addflyer <name>")

    name = message.command[1]
    caption = " ".join(message.command[2:]) if len(message.command) > 2 else ""
    flyers = load_flyers()
    flyers[name] = {
        "file_id": message.photo.file_id,
        "caption": caption
    }
    save_flyers(flyers)
    await message.reply(f"✅ Flyer '{name}' saved.")

@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /flyer <name>")
    name = message.command[1]
    flyers = load_flyers()
    flyer = flyers.get(name)
    if flyer:
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
    else:
        await message.reply("❌ Flyer not found.")

@Client.on_message(filters.command("deleteflyer"))
async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete flyers.")
    if len(message.command) < 2:
        return await message.reply("Usage: /deleteflyer <name>")
    name = message.command[1]
    flyers = load_flyers()
    if name in flyers:
        del flyers[name]
        save_flyers(flyers)
        await message.reply(f"🗑️ Flyer '{name}' deleted.")
    else:
        await message.reply("❌ Flyer not found.")

@Client.on_message(filters.command("listflyers"))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers()
    if flyers:
        names = "\n".join([f"• <code>{name}</code>" for name in flyers])
        await message.reply(f"📂 Saved Flyers:\n{names}", parse_mode="html")
    else:
        await message.reply("No flyers found.")

# ─────────────── Schedule Commands ───────────────────

@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")
    try:
        _, name, time_str, target_chat = message.text.split(maxsplit=3)
        run_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        schedule = load_schedule()
        schedule.append({
            "type": "flyer",
            "name": name,
            "chat_id": int(target_chat),
            "time": run_time.isoformat()
        })
        save_schedule(schedule)
        await message.reply(f"🕒 Scheduled flyer '{name}' to post in {target_chat} at {run_time}.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}\nUsage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <chat_id>")

@Client.on_message(filters.command("scheduletext"))
async def schedule_text(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule posts.")
    try:
        _, time_str, target_chat, *text_parts = message.text.split()
        run_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        text = " ".join(text_parts)
        schedule = load_schedule()
        schedule.append({
            "type": "text",
            "text": text,
            "chat_id": int(target_chat),
            "time": run_time.isoformat()
        })
        save_schedule(schedule)
        await message.reply(f"🕒 Scheduled message for {target_chat} at {run_time}.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}\nUsage: /scheduletext <YYYY-MM-DD HH:MM> <chat_id> <text>")

# ─────────────── Scheduler Runner ───────────────────

def schedule_jobs(scheduler: BackgroundScheduler, client: Client):
    for job in load_schedule():
        trigger = {
            "trigger": "date",
            "run_date": job["time"]
        }
        if job["type"] == "flyer":
            scheduler.add_job(send_scheduled_flyer, trigger, args=[client, job])
        elif job["type"] == "text":
            scheduler.add_job(send_scheduled_text, trigger, args=[client, job])

async def send_scheduled_flyer(client: Client, job):
    flyers = load_flyers()
    flyer = flyers.get(job["name"])
    if flyer:
        await client.send_photo(job["chat_id"], flyer["file_id"], caption=flyer["caption"])

async def send_scheduled_text(client: Client, job):
    await client.send_message(job["chat_id"], job["text"])

# ─────────────── Register ───────────────────

def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(add_flyer)
    app.add_handler(send_flyer)
    app.add_handler(delete_flyer)
    app.add_handler(list_flyers)
    app.add_handler(schedule_flyer)
    app.add_handler(schedule_text)
    schedule_jobs(scheduler, app)
