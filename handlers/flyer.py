import os
import json
import logging
from pytz import timezone as pytz_timezone
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── Logging ───────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Superusers ────────────────────────────────────────
SUPERUSERS = {6964994611}

# ─── Chat Shortcuts from env ───────────────────────────
CHAT_SHORTCUTS = {}
for name in ["SUCCUBUS_SANCTUARY", "MODELS_CHAT", "TEST_GROUP"]:
    val = os.getenv(name)
    if val:
        try:
            CHAT_SHORTCUTS[name.lower()] = int(val)
        except ValueError:
            pass

# ─── Storage paths ────────────────────────────────────
FLYER_DIR = "flyers"
SCHEDULE_FILE = "scheduled_flyers.json"
os.makedirs(FLYER_DIR, exist_ok=True)

def flyer_file(chat_id: int) -> str:
    return os.path.join(FLYER_DIR, f"{chat_id}.json")

def load_flyers(chat_id: int) -> dict:
    path = flyer_file(chat_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_flyers(chat_id: int, data: dict):
    with open(flyer_file(chat_id), "w") as f:
        json.dump(data, f, indent=2)

def load_scheduled() -> list:
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    return []

def save_scheduled(jobs: list):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(jobs, f, indent=2)

# ─── Admin check ──────────────────────────────────────
async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id in SUPERUSERS:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except:
        return False

# ─── Resolve numeric ID or shortcut ────────────────────
def resolve_target(name: str) -> int:
    try:
        return int(name)
    except ValueError:
        key = name.lower()
        if key in CHAT_SHORTCUTS:
            return CHAT_SHORTCUTS[key]
        raise ValueError(f"Unknown chat shortcut or invalid ID: {name}")

# ─── Job executors ────────────────────────────────────
async def _send_flyer(client: Client, job: dict):
    logger.info("🏷 Running flyer job %r", job)
    try:
        await client.get_chat(job["chat_id"])
    except:
        pass
    flyers = load_flyers(job["origin_chat_id"])
    f = flyers.get(job["name"])
    if not f:
        logger.warning("🏷 Flyer %r not found in %s", job["name"], job["origin_chat_id"])
        return
    try:
        await client.send_photo(
            job["chat_id"],
            f["file_id"],
            caption=f["caption"]
        )
        logger.info("🏷 Flyer sent successfully to %s", job["chat_id"])
    except Exception:
        logger.exception("🏷 Failed to send flyer")

# ─── Register handlers ────────────────────────────────
def register(app: Client, scheduler):
    # Flyer CRUD
    @app.on_message(filters.command("addflyer") & filters.photo)
    async def addflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        parts = (message.caption or "").split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name> [caption]")
        name = parts[1].strip()
        caption_text = parts[2].strip() if len(parts) == 3 else name
        flyers = load_flyers(message.chat.id)
        if name in flyers:
            return await message.reply(f"❌ Flyer “{name}” already exists.")
        flyers[name] = {"file_id": message.photo.file_id, "caption": caption_text}
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” added.")

    @app.on_message(filters.command("flyer"))
    async def flyer_cmd(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = message.command[1]
        flyers = load_flyers(message.chat.id)
        f = flyers.get(name)
        if not f:
            return await message.reply("❌ Flyer not found.")
        await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message: Message):
        flyers = load_flyers(message.chat.id)
        if not flyers:
            return await message.reply("❌ No flyers.")
        text = "<b>📌 Flyers:</b>
"
        for k, v in flyers.items():
            text += f"• <code>{k}</code> — {v['caption']}
"
        await message.reply(text)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = message.command[1]
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        del flyers[name]
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” deleted.")

    # Scheduling with optional days of week support
    @app.on_message(filters.command("scheduleflyer"))
    async def scheduleflyer(client, message: Message):
        parts = message.command
        origin = message.chat.id
        # defaults
        day_of_week = '*'
        # Usage variations:
        # 1) /scheduleflyer <name> <HH:MM> <dest>
        # 2) /scheduleflyer <name> <HH:MM> <days> <dest>
        # 3) /scheduleflyer <source> <name> <HH:MM> <dest>
        # 4) /scheduleflyer <source> <name> <HH:MM> <days> <dest>
        try:
            # identify time position
            if len(parts) == 4:
                name, time_str, dest = parts[1], parts[2], parts[3]
            elif len(parts) == 5 and (',' in parts[3] or parts[3].lower() in ['daily','weekdays','weekends']):
                name, time_str, days, dest = parts[1], parts[2], parts[3].lower(), parts[4]
                if days == 'daily': day_of_week = '*'
                elif days == 'weekdays': day_of_week = 'mon,tue,wed,thu,fri'
                elif days == 'weekends': day_of_week = 'sat,sun'
                else: day_of_week = days
            elif len(parts) == 5:
                origin = resolve_target(parts[1])
                name, time_str, dest = parts[2], parts[3], parts[4]
            elif len(parts) == 6:
                origin = resolve_target(parts[1])
                name, time_str, days, dest = parts[2], parts[3], parts[4].lower(), parts[5]
                if days == 'daily': day_of_week = '*'
                elif days == 'weekdays': day_of_week = 'mon,tue,wed,thu,fri'
                elif days == 'weekends': day_of_week = 'sat,sun'
                else: day_of_week = days
            else:
                raise ValueError
        except ValueError:
            return await message.reply(
                "❌ Usage:
"
                "/scheduleflyer <name> <HH:MM> [<days>] <dest_chat>
"
                "or
"
                "/scheduleflyer <source> <name> <HH:MM> [<days>] <dest_chat>"
            )
        try:
            hour, minute = map(int, time_str.split(':'))
            dest_id = resolve_target(dest)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        flyers = load_flyers(origin)
        if name not in flyers:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        job = {"type":"flyer","name":name,"time":time_str,
               "origin_chat_id":origin,"chat_id":dest_id,
               "day_of_week":day_of_week}
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_flyer,
            trigger='cron', day_of_week=day_of_week,
            hour=hour, minute=minute,
            timezone=pytz_timezone(os.getenv('SCHEDULER_TZ','America/Los_Angeles')),
            args=[app, job]
        )
        await message.reply(
            f"✅ Scheduled flyer “{name}” at {time_str} ({day_of_week}) → {dest_id}."
        )

    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        data = load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        text = "<b>⏰ Scheduled Flyers:</b>
"
        for i, j in enumerate(data, 1):
            text += f"{i}. {j['name']} @ {j['time']} ({j.get('day_of_week','*')}) → {j['chat_id']}
"
        await message.reply(text)

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        parts = message.command
        if len(parts)!=2 or not parts[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        idx = int(parts[1]) - 1
        data = load_scheduled()
        if idx<0 or idx>=len(data):
            return await message.reply("❌ Invalid index.")
        data.pop(idx)
        save_scheduled(data)
        await message.reply(f"✅ Canceled scheduled post #{idx+1}.")

    # Reschedule on startup
    for job in load_scheduled():
        hour, minute = map(int, job['time'].split(':'))
        scheduler.add_job(
            _send_flyer,
            trigger='cron', day_of_week=job.get('day_of_week','*'),
            hour=hour, minute=minute,
            timezone=pytz_timezone(os.getenv('SCHEDULER_TZ','America/Los_Angeles')),
            args=[app, job]
        )
