import os
import json
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from utils.check_admin import is_admin

FLYER_FILE = "data/flyers.json"
SCHEDULE_FILE = "data/scheduled_posts.json"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Load flyers
def load_flyers():
    if not os.path.exists(FLYER_FILE):
        return {}
    with open(FLYER_FILE, "r") as f:
        return json.load(f)

def save_flyers(flyers):
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=2)

# Load scheduled posts
def load_schedules():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    with open(SCHEDULE_FILE, "r") as f:
        return json.load(f)

def save_schedules(schedules):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedules, f, indent=2)

# /addflyer <name> <caption>
@Client.on_message(filters.command("addflyer"))
async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can create flyers.")
        return

    if not message.photo:
        await message.reply("❌ Please send an image with the caption: /addflyer <name> <caption>")
        return

    args = message.text.split(None, 2)
    if len(args) < 3:
        await message.reply("❌ Usage: /addflyer <name> <caption>")
        return

    name, caption = args[1], args[2]
    file_id = message.photo.file_id
    flyers = load_flyers()
    flyers[name] = {"file_id": file_id, "caption": caption}
    save_flyers(flyers)
    await message.reply(f"✅ Flyer '{name}' saved!")

# /flyer <name>
@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        await message.reply("❌ Usage: /flyer <name>")
        return

    name = args[1]
    flyers = load_flyers()
    flyer = flyers.get(name)

    if not flyer:
        await message.reply("❌ Flyer not found.")
        return

    await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])

# /scheduleflyer <name> <YYYY-MM-DD HH:MM> <target_chat_id>
@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can schedule flyers.")
        return

    args = message.text.split(None, 4)
    if len(args) < 4:
        await message.reply("❌ Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <target_chat_id>")
        return

    name, timestr, target_chat_id = args[1], args[2] + " " + args[3], args[4]
    flyers = load_flyers()
    flyer = flyers.get(name)

    if not flyer:
        await message.reply("❌ Flyer not found.")
        return

    try:
        post_time = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Invalid time format. Use YYYY-MM-DD HH:MM")
        return

    schedules = load_schedules()
    schedules.append({
        "type": "flyer",
        "name": name,
        "chat_id": int(target_chat_id),
        "time": post_time.isoformat()
    })
    save_schedules(schedules)
    await message.reply(f"✅ Flyer '{name}' scheduled for {timestr} in chat {target_chat_id}.")

# /scheduletext <YYYY-MM-DD HH:MM> <target_chat_id> <message...>
@Client.on_message(filters.command("scheduletext"))
async def schedule_text(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        await message.reply("❌ Only admins can schedule text posts.")
        return

    args = message.text.split(None, 4)
    if len(args) < 5:
        await message.reply("❌ Usage: /scheduletext <YYYY-MM-DD HH:MM> <target_chat_id> <message>")
        return

    timestr, target_chat_id, text = args[1] + " " + args[2], args[3], args[4]

    try:
        post_time = datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("❌ Invalid time format. Use YYYY-MM-DD HH:MM")
        return

    schedules = load_schedules()
    schedules.append({
        "type": "text",
        "chat_id": int(target_chat_id),
        "time": post_time.isoformat(),
        "text": text
    })
    save_schedules(schedules)
    await message.reply(f"✅ Text scheduled for {timestr} in chat {target_chat_id}.")

# Load and execute scheduled posts
def schedule_jobs(scheduler: BackgroundScheduler, client: Client):
    schedules = load_schedules()
    for job in schedules:
        trigger = DateTrigger(run_date=datetime.datetime.fromisoformat(job["time"]))
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

# /testadmin
@Client.on_message(filters.command("testadmin"))
async def test_admin_status(client: Client, message: Message):
    admin = await is_admin(client, message.chat.id, message.from_user.id)
    await message.reply(f"✅ Admin status: <b>{admin}</b>")

# Register all handlers
def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(add_flyer)
    app.add_handler(send_flyer)
    app.add_handler(schedule_flyer)
    app.add_handler(schedule_text)
    app.add_handler(test_admin_status)
    schedule_jobs(scheduler, app)

