import os
import json
import logging
from pytz import timezone as tz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Paths
BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FLYER_DIR = os.path.join(PROJECT_ROOT, 'flyers')
SCHEDULE_FILE = os.path.join(PROJECT_ROOT, 'scheduled_flyers.json')

# Ensure storage directory
os.makedirs(FLYER_DIR, exist_ok=True)

# JSON helpers
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        logger.exception(f"Failed to load JSON from {path}")
    return default

def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception(f"Failed to save JSON to {path}")

# Storage functions
def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id: int) -> dict:
    flyers = load_json(flyer_file(chat_id), {})
    logger.debug(f"Loaded {len(flyers)} flyers for chat {chat_id}")
    return flyers

def save_flyers(chat_id: int, flyers: dict):
    save_json(flyer_file(chat_id), flyers)
    logger.debug(f"Saved {len(flyers)} flyers for chat {chat_id}")

def load_scheduled() -> list:
    jobs = load_json(SCHEDULE_FILE, [])
    logger.debug(f"Loaded {len(jobs)} scheduled jobs")
    return jobs

def save_scheduled(jobs: list):
    save_json(SCHEDULE_FILE, jobs)
    logger.debug(f"Persisted {len(jobs)} scheduled jobs")

# ─── Flyer Management Commands ─────────────────────
@Client.on_message(filters.command("addflyer") & filters.photo)
async def add_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can add flyers.")
    parts = (message.caption or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /addflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name in flyers:
        return await message.reply("❌ Flyer already exists.")
    flyers[name] = {"file_id": message.photo.file_id, "caption": message.caption or name}
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' added.")

@Client.on_message(filters.command("changeflyer") & filters.photo)
async def change_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can change flyers.")
    parts = (message.caption or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /changeflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    flyers[name]["file_id"] = message.photo.file_id
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' updated.")

@Client.on_message(filters.command("deleteflyer"))
async def delete_flyer(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete flyers.")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    del flyers[name]
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' deleted.")

@Client.on_message(filters.command("listflyers"))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers(message.chat.id)
    if not flyers:
        return await message.reply("❌ No flyers.")
    lines = ["📂 <b>Flyers:</b>"] + [f"• <code>{n}</code>" for n in flyers]
    await message.reply("\n".join(lines))

@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    f = flyers.get(name)
    if not f:
        return await message.reply("❌ Flyer not found.")
    await client.send_photo(message.chat.id, f["file_id"], caption=f['caption'])

# ─── Text Scheduling Commands ─────────────────────
@Client.on_message(filters.command("scheduletext"))
async def schedule_text_cmd(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ Usage: /scheduletext <HH:MM> <days|daily> <chat_id> <text>")
    timestr, dayspec, target = parts[1], parts[2], parts[3]
    text = " ".join(parts[4:])
    try:
        hour, minute = map(int, timestr.split(':'))
    except ValueError:
        return await message.reply("❌ Invalid time format.")
    dow = '*' if dayspec.lower() in ('daily', '*') else dayspec.lower()
    try:
        chat_id = int(target)
    except ValueError:
        return await message.reply("❌ Invalid chat_id.")
    job = {'type':'text', 'time':timestr, 'day_of_week':dow,
           'origin_chat': message.chat.id, 'target_chat': chat_id,
           'text': text}
    data = load_scheduled()
    data.append(job)
    save_scheduled(data)
    label = 'daily' if dow=='*' else dow
    await message.reply(f"✅ Scheduled text @{timestr} ({label}) -> {chat_id}")

@Client.on_message(filters.command("listscheduled"))
async def list_scheduled(client: Client, message: Message):
    data = load_scheduled()
    if not data:
        return await message.reply("❌ No scheduled jobs.")
    lines = ["⏰ <b>Scheduled:</b>"]
    for i, j in enumerate(data, 1):
        lbl = 'daily' if j['day_of_week']=='*' else j['day_of_week']
        if j['type']=='flyer':
            lines.append(f"{i}. flyer '{j['name']}' @{j['time']} ({lbl}) -> {j['target_chat']}")
        else:
            lines.append(f"{i}. text @{j['time']} ({lbl}) -> {j['target_chat']}")
    await message.reply("\n".join(lines))

@Client.on_message(filters.command("cancelflyer"))
async def cancel_flyer(client: Client, message: Message):
    parts = message.text.split()
    if len(parts)!=2 or not parts[1].isdigit():
        return await message.reply("❌ Usage: /cancelflyer <index>")
    idx = int(parts[1]) - 1
    data = load_scheduled()
    if idx<0 or idx>=len(data):
        return await message.reply("❌ Invalid index.")
    job = data.pop(idx)
    save_scheduled(data)
    await message.reply(f"✅ Canceled schedule #{idx+1}.")

# ─── Internal runners ──────────────────────────────
async def _send_flyer(client: Client, job):
    logger.info(f"Running flyer job: {job}")
    flyers = load_flyers(job['origin_chat'])
    f = flyers.get(job['name'])
    if not f:
        logger.error("Missing flyer %s", job['name'])
        return
    try:
        await client.send_photo(job['target_chat'], f['file_id'], caption=f['caption'])
        logger.info("Sent flyer to %s", job['target_chat'])
    except Exception:
        logger.exception("Failed flyer job %s", job)

async def _send_text(client: Client, job):
    logger.info(f"Running text job: {job}")
    try:
        await client.send_message(job['target_chat'], job['text'])
        logger.info("Sent text to %s", job['target_chat'])
    except Exception:
        logger.exception("Failed text job %s", job)

# ─── Registration hook ─────────────────────────────
def register(app: Client, scheduler: BackgroundScheduler):
    jobs = load_scheduled()
    logger.info(f"Rescheduling {len(jobs)} jobs on startup")
    for job in jobs:
        h, m = map(int, job['time'].split(':'))
        trigger_args = dict(
            trigger='cron', hour=h, minute=m,
            day_of_week=job.get('day_of_week','*'),
            timezone=tz(os.getenv('SCHEDULER_TZ','America/Los_Angeles'))
        )
        if job['type']=='flyer':
            scheduler.add_job(_send_flyer, **trigger_args, args=[app, job])
        else:
            scheduler.add_job(_send_text, **trigger_args, args=[app, job])

    # Wire up handlers
    app.add_handler(add_flyer)
    app.add_handler(change_flyer)
    app.add_handler(delete_flyer)
    app.add_handler(list_flyers)
    app.add_handler(send_flyer)
    app.add_handler(schedule_text_cmd)
    app.add_handler(schedule_flyer_cmd)
    app.add_handler(list_scheduled)
    app.add_handler(cancel_flyer)
