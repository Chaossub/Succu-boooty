import os
import json
import logging
from typing import Dict, Union
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message

FLYER_FILE    = "flyers.json"
SCHEDULE_FILE = "scheduled_flyers.json"
OWNER_ID      = 6964994611  # Hardcoded owner/admin

# Group aliases (read from env vars)
ALIASES = {
    "MODELS_CHAT": int(os.environ.get("MODELS_CHAT", 0)),
    "TEST_GROUP": int(os.environ.get("TEST_GROUP", 0)),
    "SUCCUBUS_SANCTUARY": int(os.environ.get("SUCCUBUS_SANCTUARY", 0)),
}

def resolve_group(chat):
    # Allow group aliases in commands (case-insensitive)
    if isinstance(chat, str):
        key = chat.upper()
        if key in ALIASES:
            return ALIASES[key]
        try:
            return int(chat)
        except Exception:
            return None
    return chat

def load_json(path: str) -> Dict:
    if os.path.isfile(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_json(path: str, data: Dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_flyers(chat_id: int):
    all_flyers = load_json(FLYER_FILE)
    return all_flyers.get(str(chat_id), {})

def save_flyers(chat_id: int, flyers: Dict):
    all_flyers = load_json(FLYER_FILE)
    all_flyers[str(chat_id)] = flyers
    save_json(FLYER_FILE, all_flyers)

def load_scheduled():
    return load_json(SCHEDULE_FILE).get("jobs", [])

def save_scheduled(jobs):
    save_json(SCHEDULE_FILE, {"jobs": jobs})

# Hardwired admin check
async def is_owner_or_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

async def _send_flyer(app, job):
    chat_id = resolve_group(job["chat_id"])
    flyers  = load_flyers(chat_id)
    name    = job["name"]
    if name in flyers:
        f = flyers[name]
        if f.get("file_id"):
            await app.send_photo(chat_id, f["file_id"], caption=f["caption"])
        else:
            await app.send_message(chat_id, f["caption"])

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    # Add flyer (photo or text)
    @app.on_message(filters.command("addflyer"))
    async def add_flyer(client, message: Message):
        # Hardwire owner as admin
        if not await is_owner_or_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")

        if message.photo:
            parts = (message.caption or "").split(None, 1)
            if len(parts) < 2:
                return await message.reply("❌ Usage: /addflyer <name> <caption>")
            name   = parts[0].strip()
            caption = parts[1].strip() if len(parts) > 1 else ""
            flyers = load_flyers(message.chat.id)
            if name in flyers:
                return await message.reply("❌ Flyer already exists.")
            flyers[name] = {"file_id": message.photo.file_id, "caption": caption}
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Graphic flyer '{name}' added.")
        else:
            parts = message.text.split(None, 2)
            if len(parts) < 3:
                return await message.reply("❌ Usage: /addflyer <name> <text>")
            name, caption = parts[1], parts[2]
            flyers = load_flyers(message.chat.id)
            if name in flyers:
                return await message.reply("❌ Flyer already exists.")
            flyers[name] = {"file_id": None, "caption": caption}
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Text flyer '{name}' added.")

    @app.on_message(filters.command("flyer"))
    async def send_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name   = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        f = flyers[name]
        if f.get("file_id"):
            await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])
        else:
            await client.send_message(message.chat.id, f["caption"])

    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message: Message):
        if not await is_owner_or_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name   = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        del flyers[name]
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer '{name}' deleted.")

    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message: Message):
        flyers = load_flyers(message.chat.id)
        if not flyers:
            return await message.reply("ℹ️ No flyers found.")
        names = "\n".join(f"- {n}" for n in flyers)
        await message.reply(f"📋 Flyers:\n{names}")

    @app.on_message(filters.command("changeflyer"))
    async def change_flyer(client, message: Message):
        if not await is_owner_or_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        # Can update text or graphic flyers
        if message.photo:
            parts = (message.caption or "").split(None, 1)
            if len(parts) < 2:
                return await message.reply("❌ Usage: /changeflyer <name> <caption>")
            name = parts[0].strip()
            caption = parts[1].strip() if len(parts) > 1 else ""
            flyers = load_flyers(message.chat.id)
            if name not in flyers:
                return await message.reply("❌ Flyer not found.")
            flyers[name] = {"file_id": message.photo.file_id, "caption": caption}
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Graphic flyer '{name}' updated.")
        else:
            parts = message.text.split(None, 2)
            if len(parts) < 3:
                return await message.reply("❌ Usage: /changeflyer <name> <text>")
            name, caption = parts[1], parts[2]
            flyers = load_flyers(message.chat.id)
            if name not in flyers:
                return await message.reply("❌ Flyer not found.")
            flyers[name] = {"file_id": None, "caption": caption}
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Text flyer '{name}' updated.")

    # Schedule flyer to any group (by alias or ID)
    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not await is_owner_or_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.text.split(None, 5)
        if len(parts) < 5:
            return await message.reply(
                "❌ Usage: /scheduleflyer <flyer_name> <group> <HH:MM> <day|once>"
            )
        flyer_name, group_str, timestr, day = parts[1], parts[2], parts[3], parts[4]
        group_id = resolve_group(group_str)
        if not group_id:
            return await message.reply("❌ Unknown group/alias.")
        flyers = load_flyers(group_id)
        if flyer_name not in flyers:
            return await message.reply("❌ Flyer not found in target group.")
        try:
            hour, minute = map(int, timestr.split(":"))
        except Exception:
            return await message.reply("❌ Invalid time format.")
        job = {
            "chat_id": group_id,
            "name": flyer_name,
            "time": timestr,
            "day_of_week": day,
            "run_once": (day == "once"),
        }
        jobs = load_scheduled()
        jobs.append(job)
        save_scheduled(jobs)
        if day == "once":
            scheduler.add_job(
                _send_flyer, "date",
                run_date=None,  # You can add date param parsing here
                args=[app, job]
            )
            await message.reply(f"✅ One-time flyer '{flyer_name}' scheduled for {group_str} at {timestr}.")
        else:
            scheduler.add_job(
                _send_flyer,
                trigger="cron",
                hour=hour,
                minute=minute,
                day_of_week=day,
                timezone=scheduler.timezone,
                args=[app, job]
            )
            await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {group_str} every {day} at {timestr}.")

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        if not await is_owner_or_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        parts = message.text.split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <flyer_name>")
        name = parts[1].strip()
        jobs = load_schedule_
