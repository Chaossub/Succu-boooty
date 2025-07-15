# handlers/flyer.py

import os
import logging
import asyncio
from datetime import datetime, timedelta

from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

SUPER_ADMIN_ID = 6964994611
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB_NAME")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_col = db.flyers

# Support group aliases from ENV
ALIASES = {
    "MODELS_CHAT": int(os.environ["MODELS_CHAT"]),
    "TEST_GROUP": int(os.environ["TEST_GROUP"]),
    "SUCCUBUS_SANCTUARY": int(os.environ["SUCCUBUS_SANCTUARY"]),
}
# Also allow ID as string
for alias, cid in list(ALIASES.items()):
    ALIASES[str(cid)] = cid

def resolve_group(val):
    val = val.strip().upper()
    if val in ALIASES:
        return ALIASES[val]
    try:
        return int(val)
    except Exception:
        return None

def is_admin(user_id):
    return user_id == SUPER_ADMIN_ID

async def send_flyer(app, flyer, chat_id):
    if flyer["type"] == "photo":
        await app.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])
    elif flyer["type"] == "text":
        await app.send_message(chat_id, flyer["caption"])
    else:
        await app.send_message(chat_id, "❌ Flyer format error.")

async def scheduled_job(app, flyer_id, chat_id):
    flyer = flyers_col.find_one({"_id": flyer_id})
    if flyer:
        await send_flyer(app, flyer, chat_id)

def schedule_async_job(app, flyer_id, chat_id):
    # Runs from APScheduler in its own thread, so push to Pyrogram's loop
    asyncio.run_coroutine_threadsafe(scheduled_job(app, flyer_id, chat_id), app.loop)

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    # Add flyer (text or photo, no reply required)
    @app.on_message(filters.command("addflyer") & (filters.photo | filters.text))
    async def add_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")
        parts = (message.caption if message.photo else message.text).split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")
        name = parts[1].strip()
        caption = parts[2].strip() if len(parts) > 2 else ""
        existing = flyers_col.find_one({"name": name})
        if existing:
            return await message.reply("❌ Flyer already exists.")
        flyer = {
            "name": name,
            "type": "photo" if message.photo else "text",
            "caption": caption,
            "file_id": message.photo.file_id if message.photo else None,
            "created_by": message.from_user.id,
        }
        flyers_col.insert_one(flyer)
        await message.reply(f"✅ {'Photo' if flyer['type']=='photo' else 'Text'} flyer '{name}' added.")

    # List flyers
    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message: Message):
        flyers = list(flyers_col.find())
        if not flyers:
            return await message.reply("ℹ️ No flyers found.")
        lines = [f"<b>Flyers:</b>"] + [f"- <code>{f['name']}</code> ({f['type']})" for f in flyers]
        await message.reply("\n".join(lines))

    # Send flyer
    @app.on_message(filters.command("flyer"))
    async def get_flyer(client, message: Message):
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = parts[1].strip()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await send_flyer(app, flyer, message.chat.id)

    # Delete flyer
    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = parts[1].strip()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        flyers_col.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # Change flyer image/text
    @app.on_message(filters.command("changeflyer") & (filters.photo | filters.text))
    async def change_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")
        parts = (message.caption if message.photo else message.text).split(None, 2)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> <new_caption>")
        name = parts[1].strip()
        caption = parts[2].strip() if len(parts) > 2 else ""
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        update = {"caption": caption}
        if message.photo:
            update["type"] = "photo"
            update["file_id"] = message.photo.file_id
        else:
            update["type"] = "text"
            update["file_id"] = None
        flyers_col.update_one({"name": name}, {"$set": update})
        await message.reply(f"✅ Flyer '{name}' updated.")

    # Schedule flyer (daily or once)
    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")
        parts = message.text.split(None, 4)
        if len(parts) < 4:
            return await message.reply(
                "❌ Usage: /scheduleflyer <flyer_name> <group> <HH:MM> [daily|once] (default once)"
            )
        flyer_name = parts[1]
        group = parts[2]
        tgt_chat = resolve_group(group)
        if not tgt_chat:
            return await message.reply("❌ Invalid group alias or chat ID.")
        time_str = parts[3]
        mode = (parts[4] if len(parts) > 4 else "once").lower()
        flyer = flyers_col.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception:
            return await message.reply("❌ Invalid time format.")
        job_id = f"{flyer_name}_{tgt_chat}_{mode}"
        # Remove existing job with same id
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        # Schedule
        if mode == "daily":
            scheduler.add_job(
                schedule_async_job,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[app, flyer["_id"], tgt_chat],
                id=job_id,
                replace_existing=True,
            )
            await message.reply(f"✅ Scheduled flyer '{flyer_name}' daily to {group} at {time_str}.")
        else:
            now = datetime.now()
            run_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_date < now:
                run_date += timedelta(days=1)
            scheduler.add_job(
                schedule_async_job,
                trigger="date",
                run_date=run_date,
                args=[app, flyer["_id"], tgt_chat],
                id=job_id,
            )
            await message.reply(
                f"✅ Scheduled flyer '{flyer_name}' to {group} at {run_date.strftime('%H:%M')} (once)."
            )

    # Schedule text (for one-off scheduled text, not flyer)
    @app.on_message(filters.command("scheduletext"))
    async def schedule_text(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can schedule text.")
        parts = message.text.split(None, 4)
        if len(parts) < 4:
            return await message.reply(
                "❌ Usage: /scheduletext <group> <HH:MM> <text> [daily|once] (default once)"
            )
        group = parts[1]
        tgt_chat = resolve_group(group)
        if not tgt_chat:
            return await message.reply("❌ Invalid group alias or chat ID.")
        time_str = parts[2]
        text = parts[3]
        mode = (parts[4] if len(parts) > 4 else "once").lower()
        try:
            hour, minute = map(int, time_str.split(":"))
        except Exception:
            return await message.reply("❌ Invalid time format.")
        job_id = f"text_{tgt_chat}_{hash(text)}_{mode}"
        # Remove existing job with same id
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        async def send_text():
            await app.send_message(tgt_chat, text)
        def schedule_send_text():
            asyncio.run_coroutine_threadsafe(send_text(), app.loop)
        if mode == "daily":
            scheduler.add_job(
                schedule_send_text,
                trigger="cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True,
            )
            await message.reply(f"✅ Scheduled text daily to {group} at {time_str}.")
        else:
            now = datetime.now()
            run_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_date < now:
                run_date += timedelta(days=1)
            scheduler.add_job(
                schedule_send_text,
                trigger="date",
                run_date=run_date,
                id=job_id,
            )
            await message.reply(
                f"✅ Scheduled text to {group} at {run_date.strftime('%H:%M')} (once)."
            )

    # List scheduled jobs
    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("ℹ️ No scheduled posts.")
        lines = [f"<b>Scheduled Posts:</b>"]
        for j in jobs:
            lines.append(f"- <code>{j.id}</code> (Next: {j.next_run_time})")
        await message.reply("\n".join(lines))

    # Cancel flyer
    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        parts = message.text.split(None, 1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = parts[1].strip()
        try:
            scheduler.remove_job(job_id)
            await message.reply(f"✅ Canceled scheduled flyer '{job_id}'.")
        except Exception:
            await message.reply("❌ No such scheduled flyer/job.")

