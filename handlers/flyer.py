# handlers/flyer.py

import os
import json
import logging
from pytz import timezone as pytz_timezone
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── Set up logging ───────────────────────────────────
logger = logging.getLogger(__name__)

# ─── Superuser override ─────────────────────────────────
SUPERUSERS = {6964994611}

# ─── Chat shortcuts from environment ─────────────────────────
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

# ─── Resolve chat shortcuts or numeric IDs ─────────────
def resolve_target(target: str) -> int:
    try:
        return int(target)
    except ValueError:
        key = target.lower()
        if key in CHAT_SHORTCUTS:
            return CHAT_SHORTCUTS[key]
        raise ValueError(f"Unknown chat shortcut or invalid ID: {target}")

# ─── Job executors ────────────────────────────────────
async def _send_flyer(client: Client, job: dict):
    logger.info("🏷 [_send_flyer] running job %r", job)
    try:
        await client.get_chat(job["chat_id"])
    except:
        pass
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    flyers = load_flyers(job["origin_chat_id"])
    f = flyers.get(job["name"])
    if not f:
        logger.warning("🏷 [_send_flyer] flyer %r not found in origin %s",
                       job["name"], job["origin_chat_id"])
        return
    try:
        msg = await client.send_photo(
            job["chat_id"],
            f["file_id"],
            caption=f["caption"],
            **kwargs
        )
        logger.info("🏷 [_send_flyer] sent! message_id=%s", msg.message_id)
    except Exception:
        logger.exception("🏷 [_send_flyer] FAILED to send flyer")

async def _send_text(client: Client, job: dict):
    logger.info("✉️ [_send_text] running job %r", job)
    try:
        await client.get_chat(job["chat_id"])
    except:
        pass
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    try:
        msg = await client.send_message(job["chat_id"], job["text"], **kwargs)
        logger.info("✉️ [_send_text] sent! message_id=%s", msg.message_id)
    except Exception:
        logger.exception("✉️ [_send_text] FAILED to send text")

# ─── Registration ────────────────────────────────────
def register(app: Client, scheduler):
    # ─── Flyer CRUD ─────────────────────────────────
    @app.on_message(filters.command("addflyer") & filters.photo)
    async def addflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        caption = message.caption or ""
        parts = caption.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name>")
        name = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name in flyers:
            return await message.reply(f"❌ Flyer “{name}” already exists.")
        flyers[name] = {"file_id": message.photo.file_id, "caption": name}
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” added.")

    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def changeflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        caption = message.caption or ""
        parts = caption.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")
        name = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        flyers[name]["file_id"] = message.photo.file_id
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer “{name}” updated.")

    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = message.command[1]
        flyers = load_flyers(message.chat.id)
        f = flyers.get(name)
        if not f:
            return await message.reply("❌ Flyer not found.")
        await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

    @app.on_message(filters.command("listflyers"))
    async def listflyers_handler(client, message: Message):
        flyers = load_flyers(message.chat.id)
        if not flyers:
            return await message.reply("❌ No flyers.")
        text = "<b>📌 Flyers:</b>\n" + "\n".join(f"• <code>{n}</code>" for n in flyers)
        await message.reply(text)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message: Message):
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

    # ─── Scheduling Commands (private or group) ──────────────────────────
    @app.on_message(filters.command("scheduleflyer"))
    async def scheduleflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.command
        if len(parts) not in (4, 5):
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <chat> [<thread_id>]")
        name, time_str, target = parts[1], parts[2], parts[3]
        thread_id = int(parts[4]) if len(parts) == 5 else None
        try:
            hour, minute = map(int, time_str.split(":"))
            dest = resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        job = {
            "type": "flyer",
            "name": name,
            "time": time_str,
            "chat_id": dest,
            "origin_chat_id": message.chat.id,
            "thread_id": thread_id
        }
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_flyer,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.getenv("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )
        await message.reply(f"✅ Scheduled flyer “{name}” at {time_str} → {dest} (thread={thread_id}).")

    @app.on_message(filters.command("scheduletext"))
    async def scheduletext_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        parts = message.command
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <chat> [<thread_id>] <text>")
        time_str, target = parts[1], parts[2]
        idx, thread_id = 3, None
        if parts[3].isdigit():
            thread_id, idx = int(parts[3]), 4
        text = " ".join(parts[idx:])
        try:
            hour, minute = map(int, time_str.split(":"))
            dest = resolve_target(target)
        except Exception as e:
            return await message.reply(f"❌ {e}")
        job = {
            "type": "text",
            "time": time_str,
            "chat_id": dest,
            "text": text,
            "thread_id": thread_id
        }
        data = load_scheduled() + [job]
        save_scheduled(data)
        scheduler.add_job(
            _send_text,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.getenv("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )
        await message.reply(f"✅ Scheduled text at {time_str} → {dest} (thread={thread_id}).")

    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled_handler(client, message: Message):
        data = load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        lines = []
        for i, j in enumerate(data, 1):
            ti = f" thread={j.get('thread_id')}" if j.get("thread_id") else ""
            if j["type"] == "flyer":
                lines.append(f"{i}. Flyer '{j['name']}' @ {j['time']} → {j['chat_id']}{ti}")
            else:
                lines.append(f"{i}. Text @ {j['time']} → {j['chat_id']}{ti}: {j['text']}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer_handler(client, message: Message):
        parts = message.command
        if len(parts) != 2 or not parts[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        idx = int(parts[1]) - 1
        data = load_scheduled()
        if idx < 0 or idx >= len(data):
            return await message.reply("❌ Invalid index.")
        data.pop(idx)
        save_scheduled(data)
        await message.reply(f"✅ Canceled scheduled post #{idx+1}.")

    # ─── Reschedule on startup ──────────────────────────
    for job in load_scheduled():
        hour, minute = map(int, job["time"].split(":"))
        executor = _send_flyer if job["type"] == "flyer" else _send_text
        scheduler.add_job(
            executor,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.getenv("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )
