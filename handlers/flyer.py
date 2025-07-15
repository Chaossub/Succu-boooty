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

# --- Group Alias Map ---
ALIASES = {
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT")),
    "TEST_GROUP": int(os.getenv("TEST_GROUP")),
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY")),
}

def get_group_id(alias_or_id):
    if str(alias_or_id).upper() in ALIASES:
        return ALIASES[str(alias_or_id).upper()]
    try:
        return int(alias_or_id)
    except Exception:
        return alias_or_id

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

async def _send_flyer(app, job):
    flyer = job["flyer"]
    target = job["target"]
    if flyer.get("type") == "photo":
        await app.send_photo(target, flyer["file_id"], caption=flyer["caption"])
    else:
        await app.send_message(target, flyer["text"])

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    @app.on_message(filters.command("addflyer"))
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        flyers = load_flyers(message.chat.id)
        if message.photo:
            parts = (message.caption or "").split(None, 2)
            if len(parts) < 2:
                return await message.reply("❌ Usage: /addflyer <name> <caption>")
            name = parts[1]
            caption = parts[2] if len(parts) > 2 else ""
            if name in flyers:
                return await message.reply("❌ Flyer already exists.")
            flyers[name] = {
                "type": "photo",
                "file_id": message.photo.file_id,
                "caption": caption
            }
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Photo flyer '{name}' added.")
        else:
            parts = message.text.split(None, 2)
            if len(parts) < 3:
                return await message.reply("❌ Usage: /addflyer <name> <text>")
            name, text = parts[1], parts[2]
            if name in flyers:
                return await message.reply("❌ Flyer already exists.")
            flyers[name] = {
                "type": "text",
                "text": text
            }
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Text flyer '{name}' added.")

    @app.on_message(filters.command("changeflyer"))
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        flyers = load_flyers(message.chat.id)
        if message.photo:
            parts = (message.caption or "").split(None, 2)
            if len(parts) < 2:
                return await message.reply("❌ Usage: /changeflyer <name> <caption>")
            name = parts[1]
            caption = parts[2] if len(parts) > 2 else ""
            if name not in flyers:
                return await message.reply("❌ Flyer not found.")
            flyers[name] = {
                "type": "photo",
                "file_id": message.photo.file_id,
                "caption": caption
            }
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Photo flyer '{name}' updated.")
        else:
            parts = message.text.split(None, 2)
            if len(parts) < 3:
                return await message.reply("❌ Usage: /changeflyer <name> <text>")
            name, text = parts[1], parts[2]
            if name not in flyers:
                return await message.reply("❌ Flyer not found.")
            flyers[name] = {
                "type": "text",
                "text": text
            }
            save_flyers(message.chat.id, flyers)
            await message.reply(f"✅ Text flyer '{name}' updated.")

    @app.on_message(filters.command("flyer"))
    async def send_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        flyer = flyers[name]
        if flyer.get("type") == "photo":
            await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply(flyer["text"])

    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message: Message):
        flyers = load_flyers(message.chat.id)
        if not flyers:
            return await message.reply("ℹ️ No flyers found.")
        names = "\n".join(f"- {n}" for n in flyers)
        await message.reply(f"📋 Flyers:\n{names}")

    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = parts[1].strip()
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        del flyers[name]
        save_flyers(message.chat.id, flyers)
        await message.reply(f"✅ Flyer '{name}' deleted.")

    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        # /scheduleflyer <name> <HH:MM> <target_group> [daily|once|mon,tue,...]
        parts = message.text.split(None, 4)
        if len(parts) < 4:
            return await message.reply(
                "❌ Usage: /scheduleflyer <name> <HH:MM> <target_group> [daily|once|mon,tue,...]"
            )
        name, timestr, target_alias, *rest = parts[1:]
        flyers = load_flyers(message.chat.id)
        if name not in flyers:
            return await message.reply("❌ Flyer not found.")
        flyer = flyers[name]
        try:
            hour, minute = map(int, timestr.split(":"))
        except ValueError:
            return await message.reply("❌ Invalid time format. Use HH:MM (24hr).")
        target_id = get_group_id(target_alias)
        freq = rest[0].lower() if rest else "once"
        day_of_week = None
        if freq == "daily":
            trigger = "cron"
            day_of_week = "*"
        elif freq == "once":
            trigger = "date"
        else:
            trigger = "cron"
            day_of_week = freq
        jobs = load_scheduled()
        job = {
            "flyer": flyer,
            "target": target_id,
            "time": timestr,
            "trigger": trigger,
            "freq": freq,
            "day_of_week": day_of_week,
            "owner_chat_id": message.chat.id,
            "name": name
        }
        jobs.append(job)
        save_scheduled(jobs)
        if trigger == "date":
            from datetime import datetime, timedelta
            now = datetime.now()
            sched_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if sched_time < now:
                sched_time += timedelta(days=1)
            scheduler.add_job(
                _send_flyer,
                "date",
                run_date=sched_time,
                args=[app, job]
            )
            await message.reply(
                f"✅ Flyer '{name}' scheduled once at {sched_time.strftime('%Y-%m-%d %H:%M')} in {target_id}."
            )
        else:
            scheduler.add_job(
                _send_flyer,
                "cron",
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                args=[app, job]
            )
            msg = f"✅ Flyer '{name}' scheduled"
            if day_of_week == "*" or freq == "daily":
                msg += f" daily at {timestr} in {target_id}."
            else:
                msg += f" on {day_of_week} at {timestr} in {target_id}."
            await message.reply(msg)

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        parts = message.text.split(None, 3)
        if len(parts) < 3:
            return await message.reply("❌ Usage: /cancelflyer <name> <target_group>")
        name, target_alias = parts[1], parts[2]
        target_id = get_group_id(target_alias)
        jobs = load_scheduled()
        new_jobs = [
            j for j in jobs if not (
                j["name"] == name and str(j["target"]) == str(target_id)
            )
        ]
        for job in scheduler.get_jobs():
            args = getattr(job, "args", [])
            if len(args) == 2 and isinstance(args[1], dict):
                j = args[1]
                if j.get("name") == name and str(j.get("target")) == str(target_id):
                    job.remove()
        save_scheduled(new_jobs)
        await message.reply(f"✅ Canceled scheduled flyer '{name}' in {target_alias}.")

    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        jobs = load_scheduled()
        if not jobs:
            return await message.reply("ℹ️ No scheduled flyers.")
        out = ""
        for j in jobs:
            out += f"- {j['name']} to {j['target']} at {j['time']} [{j.get('freq','once')}]\n"
        await message.reply(f"📅 Scheduled Flyers:\n{out}")

    # Reschedule all cron jobs on startup
    for job in load_scheduled():
        try:
            if job.get("trigger") == "date":
                continue
            hour, minute = map(int, job["time"].split(":"))
            scheduler.add_job(
                _send_flyer,
                "cron",
                hour=hour,
                minute=minute,
                day_of_week=job.get("day_of_week", "*"),
                args=[app, job]
            )
        except Exception as e:
            logger.error(f"Failed to reschedule job: {job} ({e})")

