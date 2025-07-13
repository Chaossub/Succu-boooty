import os
import json
import logging
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.check_admin import is_admin

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        logger.exception("Failed to load JSON: %s", path)
    return default

def save_json(path, data):
    try:
        with open(path, "w") as f:
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

def load_scheduled() -> list:
    jobs = load_json(SCHEDULE_FILE, [])
    logger.debug("Loaded %d scheduled jobs", len(jobs))
    return jobs

def save_scheduled(jobs: list):
    save_json(SCHEDULE_FILE, jobs)
    logger.debug("Persisted %d scheduled jobs", len(jobs))

# ─── Flyer Commands ────────────────────────────────────────────────────────────
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
    text = "📂 <b>Flyers in this group:</b>\n" + "\n".join(f"• <code>{n}</code>" for n in flyers)
    await message.reply(text)

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
    await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

# ─── Scheduling Commands ───────────────────────────────────────────────────────
@Client.on_message(filters.command("scheduleflyer"))
async def schedule_flyer_cmd(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <days|daily> <chat_id>")
    name, timestr, dayspec, target = parts[1], parts[2], parts[3], parts[4]
    try:
        hour, minute = map(int, timestr.split(":"))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")
    dow = "*" if dayspec.lower() in ("daily", "*") else dayspec.lower()
    try:
        chat_id = int(target)
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    flyers = load_flyers(message.chat.id)
    if name not in flyers:
        return await message.reply("❌ Flyer not found.")
    job = {
        "type": "flyer",
        "name": name,
        "time": timestr,
        "day_of_week": dow,
        "origin_chat": message.chat.id,
        "target_chat": chat_id
    }
    scheduled = load_scheduled()
    scheduled.append(job)
    save_scheduled(scheduled)
    label = "daily" if dow == "*" else dow
    await message.reply(f"✅ Scheduled '{name}' @ {timestr} ({label}) → {chat_id}")

@Client.on_message(filters.command("scheduletext"))
async def schedule_text_cmd(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ Usage: /scheduletext <HH:MM> <days|daily> <chat_id> <text>")
    timestr, dayspec, target = parts[1], parts[2], parts[3]
    text = " ".join(parts[4:])
    try:
        hour, minute = map(int, timestr.split(":"))
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM.")
    dow = "*" if dayspec.lower() in ("daily", "*") else dayspec.lower()
    try:
        chat_id = int(target)
    except ValueError:
        return await message.reply("❌ Invalid chat ID.")
    job = {
        "type": "text",
        "time": timestr,
        "day_of_week": dow,
        "origin_chat": message.chat.id,
        "target_chat": chat_id,
        "text": text
    }
    scheduled = load_scheduled()
    scheduled.append(job)
    save_scheduled(scheduled)
    label = "daily" if dow == "*" else dow
    await message.reply(f"✅ Scheduled text @ {timestr} ({label}) → {chat_id}")

@Client.on_message(filters.command("listscheduled"))
async def list_scheduled_cmd(client: Client, message: Message):
    jobs = load_scheduled()
    if not jobs:
        return await message.reply("❌ No scheduled jobs.")
    lines = []
    for i, j in enumerate(jobs, 1):
        kind = j["type"]
        t = j["time"]
        dow = "daily" if j["day_of_week"] == "*" else j["day_of_week"]
        tgt = j["target_chat"]
        name = j.get("name", "(text)")
        lines.append(f"{i}. {kind} '{name}' @ {t} ({dow}) → {tgt}")
    await message.reply("⏰ <b>Scheduled jobs:</b>\n" + "\n".join(lines))

@Client.on_message(filters.command("cancelflyer"))
async def cancel_flyer_cmd(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: /cancelflyer <job_index>")
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        return await message.reply("❌ Invalid index.")
    jobs = load_scheduled()
    if idx < 0 or idx >= len(jobs):
        return await message.reply("❌ Index out of range.")
    removed = jobs.pop(idx)
    save_scheduled(jobs)
    await message.reply(f"✅ Removed scheduled job #{idx+1}: {removed}")

# ─── Internal Runners ──────────────────────────────────────────────────────────
async def _send_flyer(client: Client, job):
    logger.info("🏷 Running flyer job %s", job)
    flyers = load_flyers(job["origin_chat"])
    f = flyers.get(job["name"])
    if not f:
        return logger.error("Missing flyer %s", job["name"])
    try:
        await client.send_photo(job["target_chat"], f["file_id"], caption=f["caption"])
    except Exception:
        logger.exception("Failed flyer job %s", job)

async def _send_text(client: Client, job):
    logger.info("🏷 Running text job %s", job)
    try:
        await client.send_message(job["target_chat"], job["text"])
    except Exception:
        logger.exception("Failed text job %s", job)

# ─── Registration ─────────────────────────────────────────────────────────────
def register(app: Client, scheduler: BackgroundScheduler):
    jobs = load_scheduled()
    logger.info("Rescheduling %d jobs on startup", len(jobs))
    tzinfo = timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
    for job in jobs:
        h, m = map(int, job["time"].split(":"))
        trigger = dict(trigger="cron", hour=h, minute=m, day_of_week=job["day_of_week"], timezone=tzinfo)
        if job["type"] == "flyer":
            scheduler.add_job(_send_flyer, **trigger, args=[app, job])
        else:
            scheduler.add_job(_send_text, **trigger, args=[app, job])
