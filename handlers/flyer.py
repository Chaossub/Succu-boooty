import os
import json
import logging
from datetime import datetime, timedelta
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ─── Global Scheduler Reference ───────────────────────────────────────────────────
SCHEDULER: BackgroundScheduler = None

# ─── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FLYER_DIR = os.path.join(PROJECT_ROOT, "flyers")
SCHEDULE_FILE = os.path.join(PROJECT_ROOT, "scheduled_flyers.json")
os.makedirs(FLYER_DIR, exist_ok=True)

# ─── JSON Helpers ───────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to load JSON: %s", path)
    return default

def save_json(path, data):
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.exception("Failed to save JSON: %s", path)

# ─── Flyer Storage ─────────────────────────────────────────────────────────────
def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id: int) -> dict:
    flyers = load_json(flyer_file(chat_id), {})
    logger.debug("Loaded %d flyers for chat %s", len(flyers), chat_id)
    return flyers

def save_flyers(chat_id: int, flyers: dict):
    save_json(flyer_file(chat_id), flyers)
    logger.debug("Saved %d flyers for chat %s", len(flyers), chat_id)

# ─── Schedule Storage ──────────────────────────────────────────────────────────
def load_scheduled() -> list:
    jobs = load_json(SCHEDULE_FILE, [])
    logger.debug("Loaded %d scheduled jobs", len(jobs))
    return jobs

def save_scheduled(jobs: list):
    save_json(SCHEDULE_FILE, jobs)
    logger.debug("Persisted %d scheduled jobs", len(jobs))

# ─── Test Command ───────────────────────────────────────────────────────────────
@Client.on_message(filters.command('ping'))
async def ping(client: Client, message: Message):
    await message.reply("pong")

# ─── Flyer Commands ────────────────────────────────────────────────────────────
@Client.on_message(filters.command('addflyer') & filters.photo)
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

@Client.on_message(filters.command('changeflyer') & filters.photo)
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

@Client.on_message(filters.command('deleteflyer'))
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

@Client.on_message(filters.command('listflyers'))
async def list_flyers(client: Client, message: Message):
    flyers = load_flyers(message.chat.id)
    if not flyers:
        return await message.reply("❌ No flyers.")
    list_text = "\n".join(f"• <code>{n}</code>" for n in flyers)
    await message.reply(f"📂 <b>Flyers in this group:</b>\n{list_text}")

@Client.on_message(filters.command('flyer'))
async def send_flyer(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    flyers = load_flyers(message.chat.id)
    f = flyers.get(name)
    if not f:
        return await message.reply("❌ Flyer not found.")
    await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

# ─── Scheduling Handlers ───────────────────────────────────────────────────────
@Client.on_message(filters.command('scheduleflyer'))
async def schedule_flyer_cmd(client: Client, message: Message):
    logger.debug("[scheduleflyer] got: %s", message.text)
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")

    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        return await message.reply("❌ Usage: /scheduleflyer <HH:MM> [daily] <chat_id|ENV_VAR> <name>")

    time_str = parts[1]
    try:
        hour, minute = map(int, time_str.split(":"))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")

    tz = timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))

    if parts[2].lower() == "daily":
        repeat = True
        if len(parts) < 4:
            return await message.reply('❌ After "daily", provide
