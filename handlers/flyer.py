# handlers/flyer.py
import os
import json
import logging
from typing import Dict
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message
from utils.check_admin import is_admin

FLYER_FILE    = "flyers.json"
SCHEDULE_FILE = "scheduled_flyers.json"

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
    all_flyers            = load_json(FLYER_FILE)
    all_flyers[str(chat_id)] = flyers
    save_json(FLYER_FILE, all_flyers)

def load_scheduled():
    return load_json(SCHEDULE_FILE).get("jobs", [])

def save_scheduled(jobs):
    save_json(SCHEDULE_FILE, {"jobs": jobs})

async def _send_flyer(app, job):
    chat_id = job["chat_id"]
    flyers  = load_flyers(chat_id)
    name    = job["name"]
    if name in flyers:
        f = flyers[name]
        await app.send_photo(chat_id, f["file_id"], caption=f["caption"])

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    @app.on_message(filters.command("addflyer") & filters.photo)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        parts = (message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name>")
        name    = parts[1].strip()
        flyers  = load_flyers(message.chat.id)
        if name in flyers:
            return await message.reply("❌ Flyer already exists.")
        flyers[name] = {"file_id": message.photo.file_id, "caption": message.caption}
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer '{name}' added.")

    @app.on_message(filters.command("flyer"))
    async def send_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name   = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        f = flyers[name]
        await client.send_photo(message.chat.id, f["file_id"], caption=f["caption"])

    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(maxsplit=1)
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

    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        parts = (message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")
        name   = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        flyers[name] = {"file_id": message.photo.file_id, "caption": message.caption}
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer '{name}' updated.")

    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <day_of_week>")
        name, timestr, day = parts[1], parts[2], parts[3]
        try:
            hour, minute = map(int, timestr.split(":"))
        except ValueError:
            return await message.reply("❌ Invalid time format.")
        job = {
            "chat_id":     message.chat.id,
            "name":        name,
            "time":        timestr,
            "day_of_week": day
        }
        jobs = load_scheduled()
        jobs.append(job)
        save_scheduled(jobs)
        scheduler.add_job(
            _send_flyer,
            trigger="cron",
            hour=hour,
            minute=minute,
            day_of_week=day,
            timezone=scheduler.timezone,
            args=[app, job]
        )
        await message.reply(f"✅ Scheduled flyer '{name}' on {day} at {timestr}.")

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <name>")
        name = parts[1].strip()
        jobs     = load_scheduled()
        new_jobs = [j for j in jobs if not (j["name"] == name and j["chat_id"] == message.chat.id)]
        if len(new_jobs) == len(jobs):
            return await message.reply("ℹ️ No scheduled flyer found by that name.")
        save_scheduled(new_jobs)
        for j in scheduler.get_jobs():
            args = getattr(j, "args", [])
            if len(args) == 2 and isinstance(args[1], dict) and args[1].get("name") == name:
                j.remove()
        await message.reply(f"✅ Canceled scheduled flyer '{name}'.")
