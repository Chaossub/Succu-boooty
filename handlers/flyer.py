import os
import json
import logging
from pytz import timezone as tz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

# ─── Logging Setup ───────────────────────────────────
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ─── Storage Paths ───────────────────────────────────
FLYER_DIR = os.path.join(os.path.dirname(__file__), '..', 'flyers')
SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), '..', 'scheduled_flyers.json')

# Ensure directories exist
os.makedirs(FLYER_DIR, exist_ok=True)

# ─── JSON Helpers ────────────────────────────────────
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

# ─── Flyer Storage ───────────────────────────────────
def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id: int) -> dict:
    flyers = load_json(flyer_file(chat_id), {})
    logger.debug(f"Loaded {len(flyers)} flyers for chat {chat_id}")
    return flyers

def save_flyers(chat_id: int, flyers: dict):
    save_json(flyer_file(chat_id), flyers)
    logger.debug(f"Saved {len(flyers)} flyers for chat {chat_id}")

# ─── Scheduled Jobs Storage ──────────────────────────
def load_scheduled() -> list:
    jobs = load_json(SCHEDULE_FILE, [])
    logger.debug(f"Loaded {len(jobs)} scheduled jobs")
    return jobs

def save_scheduled(jobs: list):
    save_json(SCHEDULE_FILE, jobs)
    logger.debug(f"Persisted {len(jobs)} scheduled jobs")

# ─── Flyer Management Commands ───────────────────────
@Client.on_message(filters.command("addflyer") & filters.photo)
async def add_flyer(client: Client, message: Message):
    logger.debug(f"/addflyer by {message.from_user.id} in {message.chat.id}")
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
    logger.debug(f"/changeflyer by {message.from_user.id} in {message.chat.id}")
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can change flyers.")
    parts = (message.caption or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /changeflyer <name>")
    name = parts[1].strip()
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ No flyer found with that name.")
    flyers[name]["file_id"] = message.photo.file_id
    save_flyers(message.chat.id, flyers)
    await message.reply(f"✅ Flyer '{name}' updated.")

@Client.on_message(filters.command("deleteflyer"))
async def delete_flyer(client: Client, message: Message):
    logger.debug(f"/deleteflyer by {message.from_user.id} in {message.chat.id}")
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
    text = "📂 <b>Available Flyers:</b>\n" + "\n".join(f"• <code>{name}</code>" for name in flyers)
    await message.reply(text)

@Client.on_message(filters.command("flyer"))
async def send_flyer(client: Client, message: Message):
    logger.debug(f"/flyer in {message.chat.id}: {message.text}")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    f = flyers.get(name)
    if not f:
        return await message.reply("❌ Flyer not found.")
    await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

# ─── Scheduling Commands ─────────────────────────────
@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer_cmd(client: Client, message: Message):
    logger.debug(f"/scheduleflyer invoked: {message.text}")
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <days> <chat_id>")
    _, name, timestr, dayspec, target = parts[:5]
    try:
        hour, minute = map(int, timestr.split(':'))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")
    dow = '*' if dayspec.lower() in ('daily', '*') else dayspec.lower()
    try:
        chat_id = int(target)
    except ValueError:
        return await message.reply("❌ Invalid chat_id.")
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    job = {
        'type': 'flyer',
        'name': name,
        'time': timestr,
        'day_of_week': dow,
        'origin_chat': message.chat.id,
        'target_chat': chat_id
    }
    data = load_scheduled()
    data.append(job)
    save_scheduled(data)
    await message.reply(f"✅ Scheduled '{name}' @{timestr} ({dow}) → {chat_id}")

@Client.on_message(filters.command("listscheduled"))
async def list_scheduled(client: Client, message: Message):
    data = load_scheduled()
    if not data:
        return await message.reply("❌ No scheduled posts.")
    lines = ["⏰ <b>Scheduled Flyers:</b>"]
    for i, j in enumerate(data, 1):
        lines.append(f"{i}. <code>{j['name']}</code> at {j['time']} ({j['day_of_week']}) → {j['target_chat']}")
    await message.reply("\n".join(lines))

@Client.on_message(filters.command("cancelflyer"))
async def cancel_flyer(client: Client, message: Message):
    logger.debug(f"/cancelflyer invoked: {message.text}")
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("❌ Usage: /cancelflyer <index>")
