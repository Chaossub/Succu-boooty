import os
import logging
from typing import Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# ───── Config: Hardcoded super-admin user ID ─────
SUPER_ADMIN_ID = 6964994611

# ───── MongoDB ─────
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo.flyers  # Global flyer storage
sched_col = mongo.scheduled_flyers

# ───── Group Aliases ─────
def get_group_aliases():
    aliases = {}
    for env, val in os.environ.items():
        if env.endswith("_CHAT") or env.endswith("_GROUP") or env.endswith("_SANCTUARY"):
            aliases[env.upper()] = int(val)
    return aliases
GROUP_ALIASES = get_group_aliases()

def is_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

# ───── Flyer Storage ─────
def flyer_exists(name: str) -> bool:
    return flyers_col.find_one({"name": name.lower()}) is not None

def get_flyer(name: str) -> dict:
    return flyers_col.find_one({"name": name.lower()})

def save_flyer(name: str, data: Dict[str, Any]):
    data["name"] = name.lower()
    flyers_col.replace_one({"name": name.lower()}, data, upsert=True)

def delete_flyer(name: str):
    flyers_col.delete_one({"name": name.lower()})

def list_flyers():
    return [doc["name"] for doc in flyers_col.find({}, {"name": 1})]

# ───── Scheduling ─────
def save_schedule(job: dict):
    sched_col.insert_one(job)

def delete_schedule(job_id):
    sched_col.delete_one({"_id": job_id})

def get_schedules():
    return list(sched_col.find({}))

# ───── Sending Flyers ─────
async def send_flyer_to_group(app: Client, flyer: dict, chat_id: int):
    if flyer.get("file_id"):
        await app.send_photo(chat_id, flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await app.send_message(chat_id, flyer.get("caption", ""))

# ───── Register ─────
def register(app: Client, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    # -- Add Flyer --
    @app.on_message(filters.command("addflyer"))
    async def add_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")

        # Text or photo
        if message.photo:
            parts = (message.caption or "").split(None, 1)
        else:
            parts = message.text.split(None, 2)

        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")

        name = parts[1]
        caption = parts[2] if len(parts) > 2 else (message.caption or message.text or "")

        if flyer_exists(name):
            return await message.reply("❌ Flyer already exists.")

        if message.photo:
            file_id = message.photo.file_id
            save_flyer(name, {"file_id": file_id, "caption": caption})
        else:
            save_flyer(name, {"caption": caption})

        await message.reply(f"✅ {'Photo' if message.photo else 'Text'} flyer '{name}' added.")

    # -- Change Flyer Photo/Caption --
    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def change_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        parts = (message.caption or "").split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")
        name = parts[1]
        flyer = get_flyer(name)
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        flyer["file_id"] = message.photo.file_id
        flyer["caption"] = message.caption or flyer.get("caption", "")
        save_flyer(name, flyer)
        await message.reply(f"✅ Flyer '{name}' updated.")

    # -- Delete Flyer --
    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer_cmd(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = parts[1]
        if not flyer_exists(name):
            return await message.reply("❌ Flyer not found.")
        delete_flyer(name)
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # -- List Flyers --
    @app.on_message(filters.command("listflyers"))
    async def list_flyers_cmd(client, message: Message):
        flyers = list_flyers()
        if not flyers:
            return await message.reply("ℹ️ No flyers found.")
        await message.reply("📋 Flyers:\n" + "\n".join(f"- {n}" for n in flyers))

    # -- Get Flyer (send to current chat) --
    @app.on_message(filters.command("flyer"))
    async def send_flyer_cmd(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = parts[1]
        flyer = get_flyer(name)
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await send_flyer_to_group(client, flyer, message.chat.id)

    # -- Schedule Flyer (photo/text) --
    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        # /scheduleflyer <flyer_name> <group> <HH:MM> [once|daily]
        parts = message.text.split(None, 4)
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <group> <HH:MM> [once|daily]")

        name, group, time = parts[1], parts[2], parts[3]
        mode = parts[4] if len(parts) > 4 else "once"
        flyer = get_flyer(name)
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        # Resolve group alias, case-insensitive
        group_id = None
        for k, v in GROUP_ALIASES.items():
            if k.lower() == group.lower():
                group_id = v
                break
        if not group_id:
            try:
                group_id = int(group)
            except Exception:
                return await message.reply("❌ Invalid group.")

        hour, minute = map(int, time.split(":"))
        job = {
            "flyer_name": name,
            "group_id": group_id,
            "hour": hour,
            "minute": minute,
            "mode": mode,
        }
        save_schedule(job)
        job_func = lambda: send_flyer_to_group(app, flyer, group_id)
        if mode == "daily":
            scheduler.add_job(job_func, "cron", hour=hour, minute=minute, args=[], timezone=scheduler.timezone)
            await message.reply(f"✅ Scheduled daily flyer '{name}' in {group} at {time}.")
        else:
            scheduler.add_job(job_func, "date", run_date=f"{hour}:{minute}", args=[])
            await message.reply(f"✅ Scheduled one-time flyer '{name}' in {group} at {time}.")

    # -- Schedule Text Flyer --
    @app.on_message(filters.command("scheduletext"))
    async def schedule_text(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        # /scheduletext <HH:MM> <group> <text...>
        parts = message.text.split(None, 3)
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <group> <text>")
        time, group, text = parts[1], parts[2], parts[3]

        group_id = None
        for k, v in GROUP_ALIASES.items():
            if k.lower() == group.lower():
                group_id = v
                break
        if not group_id:
            try:
                group_id = int(group)
            except Exception:
                return await message.reply("❌ Invalid group.")

        hour, minute = map(int, time.split(":"))
        job_func = lambda: app.send_message(group_id, text)
        scheduler.add_job(job_func, "cron", hour=hour, minute=minute, timezone=scheduler.timezone)
        await message.reply(f"✅ Scheduled text flyer daily at {time} in {group}.")

    # -- List Scheduled Posts --
    @app.on_message(filters.command("listscheduled"))
    async def listscheduled(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can view scheduled posts.")
        schedules = get_schedules()
        if not schedules:
            return await message.reply("ℹ️ No scheduled posts.")
        lines = []
        for i, j in enumerate(schedules, 1):
            lines.append(f"{i}. Flyer: {j.get('flyer_name', '[text]')} → {j['group_id']} at {j['hour']:02}:{j['minute']:02} ({j.get('mode','daily')})")
        await message.reply("🗓 Scheduled Posts:\n" + "\n".join(lines))

    # -- Cancel Scheduled Post --
    @app.on_message(filters.command("cancelflyer"))
    async def cancelflyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        # /cancelflyer <index>
        parts = message.text.split(None, 1)
        if len(parts) < 2 or not parts[1].isdigit():
            return await message.reply("❌ Usage: /cancelflyer <index>")
        index = int(parts[1]) - 1
        schedules = get_schedules()
        if index < 0 or index >= len(schedules):
            return await message.reply("❌ Invalid index.")
        job = schedules[index]
        delete_schedule(job["_id"])
        await message.reply("✅ Canceled scheduled post.")

