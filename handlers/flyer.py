import os
import logging
from typing import Dict, Any
from datetime import datetime
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message

# --- Mongo Setup ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME", "SuccuBot")
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo["flyers"]
schedules_col = mongo["flyer_schedules"]

GROUP_ALIASES = {
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT")),
    "TEST_GROUP": int(os.getenv("TEST_GROUP")),
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY")),
}

SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def flyer_to_caption(f):
    if f.get("type") == "text":
        return f["caption"]
    return f.get("caption", "")

async def send_flyer(app, chat_id, flyer):
    if flyer["type"] == "photo":
        await app.send_photo(chat_id, flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await app.send_message(chat_id, flyer.get("caption", ""))

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    # Add flyer (text or photo)
    @app.on_message(filters.command("addflyer"))
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")

        parts = (message.caption or message.text).split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")

        name = parts[1].strip().lower()
        flyer = flyers_col.find_one({"name": name})

        if message.photo:
            file_id = message.photo.file_id
            flyer_doc = {
                "name": name,
                "type": "photo",
                "file_id": file_id,
                "caption": message.caption or "",
                "created": datetime.utcnow()
            }
        else:
            caption = parts[2] if len(parts) > 2 else ""
            flyer_doc = {
                "name": name,
                "type": "text",
                "caption": caption,
                "created": datetime.utcnow()
            }
        flyers_col.replace_one({"name": name}, flyer_doc, upsert=True)
        await message.reply(f"✅ {'Photo' if message.photo else 'Text'} flyer '{name}' added.")

    # Send flyer
    @app.on_message(filters.command("flyer"))
    async def get_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = parts[1].strip().lower()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await send_flyer(client, message.chat.id, flyer)

    # List flyers
    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message: Message):
        flyers = flyers_col.find()
        if flyers.count() == 0:
            return await message.reply("ℹ️ No flyers found.")
        names = [f"- <b>{f['name']}</b> ({f['type']})" for f in flyers]
        await message.reply("📋 <b>Flyers:</b>\n" + "\n".join(names))

    # Delete flyer
    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = parts[1].strip().lower()
        result = flyers_col.delete_one({"name": name})
        if result.deleted_count == 0:
            return await message.reply("❌ Flyer not found.")
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # Change flyer image/caption
    @app.on_message(filters.command("changeflyer"))
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        parts = (message.caption or message.text).split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> <caption>")
        name = parts[1].strip().lower()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if message.photo:
            file_id = message.photo.file_id
            flyers_col.update_one(
                {"name": name},
                {"$set": {"type": "photo", "file_id": file_id, "caption": message.caption or ""}}
            )
            await message.reply(f"✅ Flyer '{name}' photo updated.")
        else:
            caption = parts[2] if len(parts) > 2 else ""
            flyers_col.update_one(
                {"name": name},
                {"$set": {"type": "text", "caption": caption}}
            )
            await message.reply(f"✅ Flyer '{name}' caption updated.")

    # Schedule flyer
    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.text.split(None, 5)
        if len(parts) < 5:
            return await message.reply(
                "❌ Usage: /scheduleflyer <name> <group> <HH:MM> <once|daily>"
            )
        name = parts[1].strip().lower()
        group = parts[2].strip()
        time_str = parts[3].strip()
        repeat = parts[4].strip().lower()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        group_id = GROUP_ALIASES.get(group.upper())
        if not group_id:
            try:
                group_id = int(group)
            except Exception:
                return await message.reply("❌ Invalid group.")
        hour, minute = map(int, time_str.split(":"))
        job_id = f"{name}_{group_id}_{time_str}_{repeat}"
        schedule = {
            "job_id": job_id,
            "name": name,
            "group_id": group_id,
            "time": time_str,
            "repeat": repeat,
            "created": datetime.utcnow()
        }
        schedules_col.replace_one({"job_id": job_id}, schedule, upsert=True)
        if repeat == "daily":
            scheduler.add_job(
                send_flyer, "cron", hour=hour, minute=minute, args=[app, group_id, flyer], id=job_id, replace_existing=True
            )
        else:
            scheduler.add_job(
                send_flyer, "date", run_date=datetime.now().replace(hour=hour, minute=minute), args=[app, group_id, flyer], id=job_id, replace_existing=True
            )
        await message.reply(f"✅ Scheduled flyer '{name}' for {group} at {time_str} ({repeat}).")

    # List scheduled
    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        jobs = list(schedules_col.find())
        if not jobs:
            return await message.reply("ℹ️ No scheduled flyers.")
        lines = []
        for i, j in enumerate(jobs):
            lines.append(f"{i+1}. <b>{j['name']}</b> in <code>{j['group_id']}</code> at {j['time']} ({j['repeat']})")
        await message.reply("📅 <b>Scheduled Flyers:</b>\n" + "\n".join(lines))

    # Cancel scheduled flyer
    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can cancel flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <index>")
        try:
            idx = int(parts[1].strip()) - 1
        except:
            return await message.reply("❌ Invalid index.")
        jobs = list(schedules_col.find())
        if idx < 0 or idx >= len(jobs):
            return await message.reply("❌ Index out of range.")
        job = jobs[idx]
        schedules_col.delete_one({"job_id": job["job_id"]})
        scheduler.remove_job(job["job_id"])
        await message.reply(f"✅ Canceled scheduled flyer '{job['name']}'.")

    # Re-add scheduled jobs on startup
    for sched in schedules_col.find():
        flyer = flyers_col.find_one({"name": sched["name"]})
        if not flyer:
            continue
        group_id = sched["group_id"]
        hour, minute = map(int, sched["time"].split(":"))
        if sched["repeat"] == "daily":
            scheduler.add_job(
                send_flyer, "cron", hour=hour, minute=minute, args=[app, group_id, flyer], id=sched["job_id"], replace_existing=True
            )
        else:
            # If scheduled time is in the past, don't re-add
            now = datetime.now()
            scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled_time > now:
                scheduler.add_job(
                    send_flyer, "date", run_date=scheduled_time, args=[app, group_id, flyer], id=sched["job_id"], replace_existing=True
                )
