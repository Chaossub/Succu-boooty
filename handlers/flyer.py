# handlers/flyer.py

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
FLYER_DIR    = "flyers"
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
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("creator", "administrator")
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
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    flyers = load_flyers(job["origin_chat_id"])
    f = flyers.get(job["name"])
    if not f:
        logger.warning("🏷 Flyer %r not found in %s", job["name"], job["origin_chat_id"])
        return
    try:
        msg = await client.send_photo(
            job["chat_id"],
            f["file_id"],
            caption=f["caption"],
            **kwargs
        )
        logger.info("🏷 Flyer sent (msg_id=%s)", msg.message_id)
    except Exception:
        logger.exception("🏷 Failed to send flyer")

async def _send_text(client: Client, job: dict):
    logger.info("✉️ Running text job %r", job)
    try:
        await client.get_chat(job["chat_id"])
    except:
        pass
    kwargs = {}
    if job.get("thread_id") is not None:
        kwargs["message_thread_id"] = job["thread_id"]
    try:
        msg = await client.send_message(job["chat_id"], job["text"], **kwargs)
        logger.info("✉️ Text sent (msg_id=%s)", msg.message_id)
    except Exception:
        logger.exception("✉️ Failed to send text")

# ─── Register handlers ────────────────────────────────
def register(app: Client, scheduler):
    # Flyer CRUD
    @app.on_message(filters.command("addflyer") & filters.photo)
    async def addflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        parts = (message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name>")
        name = parts[1].strip()
        fdict = load_flyers(message.chat.id)
        if name in fdict:
            return await message.reply(f"❌ Flyer “{name}” already exists.")
        fdict[name] = {"file_id": message.photo.file_id, "caption": name}
        save_flyers(message.chat.id, fdict)
        await message.reply(f"✅ Flyer “{name}” added.")

    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def changeflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        parts = (message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")
        name = parts[1].strip()
        fdict = load_flyers(message.chat.id)
        if name not in fdict:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        fdict[name]["file_id"] = message.photo.file_id
        save_flyers(message.chat.id, fdict)
        await message.reply(f"✅ Flyer “{name}” updated.")

    @app.on_message(filters.command("flyer"))
    async def flyer_cmd(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = message.command[1]
        fdict = load_flyers(message.chat.id)
        f = fdict.get(name)
        if not f:
            return await message.reply("❌ Flyer not found.")
        await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message: Message):
        fdict = load_flyers(message.chat.id)
        if not fdict:
            return await message.reply("❌ No flyers.")
        text = "<b>📌 Flyers:</b>\n"
        for key, val in fdict.items():
            text += f"• <code>{key}</code> — {val.get('caption','')}\n"
        await message.reply(text)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = message.command[1]
        fdict = load_flyers(message.chat.id)
        if name not in fdict:
            return await message.reply(f"❌ Flyer “{name}” not found.")
        del fdict[name]
        save_flyers(message.chat.id, fdict)
        await message.reply(f"✅ Flyer “{name}” deleted.")

    # Schedule flyer: now takes a source chat + name + time + dest chat + optional thread
    @app.on_message(filters.command("scheduleflyer"))
    async def scheduleflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.command
        if len(parts) not in (5, 6):
            return await message.reply(
                "❌ Usage: /scheduleflyer <source_chat> <name> <HH:MM> <dest_chat> [<thread_id>]"
            )
        source_id  = resolve_target(parts[1])
        name       = parts[2]
        time_str   = parts[3]
        dest_id    = resolve_target(parts[4])
        thread_id  = int(parts[5]) if len(parts) == 6 else None

        fdict = load_flyers(source_id)
        if name not in fdict:
            return await message.reply(f"❌ Flyer “{name}” not found in {parts[1]}.")
        try:
            hour, minute = map(int, time_str.split(":"))
        except:
            return await message.reply("❌ Invalid time. Use HH:MM.")
        job = {
            "type": "flyer",
            "name": name,
            "time": time_str,
            "origin_chat_id": source_id,
            "chat_id": dest_id,
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
        await message.reply(f"✅ Scheduled flyer “{name}” from {parts[1]} to {parts[4]} at {time_str} (thread={thread_id}).")

    # Schedule text (same pattern for source → dest)
    @app.on_message(filters.command("scheduletext"))
    async def scheduletext(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        parts = message.command
        if len(parts) < 5:
            return await message.reply(
                "❌ Usage: /scheduletext <source_chat> <HH:MM> <dest_chat> [<thread_id>] <text>"
            )
        source_id = resolve_target(parts[1])
        time_str  = parts[2]
        dest_id   = resolve_target(parts[3])
        idx       = 4
        thread_id = None
        if parts[4].isdigit():
            thread_id = int(parts[4])
            idx += 1
        text = " ".join(parts[idx:])

        try:
            hour, minute = map(int, time_str.split(":"))
        except:
            return await message.reply("❌ Invalid time format.")
        job = {
            "type": "text",
            "time": time_str,
            "origin_chat_id": source_id,
            "chat_id": dest_id,
            "thread_id": thread_id,
            "text": text
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
        await message.reply(f"✅ Scheduled text from {parts[1]} to {parts[3]} at {time_str} (thread={thread_id}).")

    # List and cancel remain the same...
    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        data = load_scheduled()
        if not data:
            return await message.reply("❌ No scheduled posts.")
        lines = []
        for i, j in enumerate(data, 1):
            ti = f" thread={j.get('thread_id')}" if j.get("thread_id") else ""
            if j["type"] == "flyer":
                lines.append(f"{i}. Flyer '{j['name']}' from {j['origin_chat_id']} to {j['chat_id']} @ {j['time']}{ti}")
            else:
                lines.append(f"{i}. Text @ {j['time']} → from {j['origin_chat_id']} to {j['chat_id']}{ti}: {j['text']}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
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

    # Reschedule on startup
    for job in load_scheduled():
        hour, minute = map(int, job["time"].split(":"))
        fn = _send_flyer if job["type"] == "flyer" else _send_text
        scheduler.add_job(
            fn,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=pytz_timezone(os.getenv("SCHEDULER_TZ", "US/Pacific")),
            args=[app, job]
        )

