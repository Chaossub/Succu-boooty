import os
import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["flyer_db"]
flyers = db.flyers

SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

# ALIAS logic: read all *_CHAT env vars
ALIASES = {}
for k, v in os.environ.items():
    if k.endswith("_CHAT"):
        try:
            ALIASES[k] = int(v)
        except Exception:
            pass

def is_admin(user_id):
    return user_id in ADMINS

# Scheduler
jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

def resolve_group_id(group_str):
    # Try as int
    try:
        return int(group_str)
    except ValueError:
        pass
    # Try as alias
    alias = group_str.strip().upper()
    if alias in ALIASES:
        return ALIASES[alias]
    return None

async def post_flyer_job(client, group_id, flyer_name, chat_id):
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        return
    if flyer.get("photo_id"):
        await client.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
    else:
        await client.send_message(group_id, flyer.get("caption", ""))

def register(app):

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")
        args = message.text.strip().split()
        if len(args) < 6:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_id or shortcut>\n"
                "Example: /scheduleflyer tipping 2025-07-16 15:09 once MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_str = args[5]

        group_id = resolve_group_id(group_str)
        if group_id is None:
            return await message.reply("Invalid group_id or group shortcut!")

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Calculate run time in scheduler timezone
        try:
            run_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            tz = pytz.timezone(SCHED_TZ)
            run_time = tz.localize(run_time)
        except Exception as e:
            return await message.reply(f"Invalid date/time format: {e}")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M')}"

        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=run_time.hour,
                minute=run_time.minute,
                id=job_id,
                replace_existing=True,
                args=[client, group_id, flyer_name, message.chat.id],
            )
        else:
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=run_time,
                id=job_id,
                replace_existing=True,
                args=[client, group_id, flyer_name, message.chat.id],
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' for {run_time.strftime('%Y-%m-%d %H:%M')} in <code>{group_id}</code> ({repeat}).\nJob ID: <code>{job_id}</code>",
            parse_mode="html"
        )

    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No scheduled flyers.")
        lines = ["📅 Scheduled Flyers:"]
        for job in jobs:
            lines.append(f"• {job.id}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancelflyer_handler(client, message: Message):
        args = message.text.strip().split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("No job found with that ID.")
        scheduler.remove_job(job_id)
        await message.reply(f"❌ Scheduled flyer <code>{job_id}</code> canceled.", parse_mode="html")

# Call handlers.flyer_scheduler.register(app) in main.py

