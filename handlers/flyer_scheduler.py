import os
import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# ---- CONFIG ----
MONGO_URI = os.getenv("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["flyer_db"]
flyers = db.flyers

SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

def is_admin(user_id):
    return user_id in ADMINS

def resolve_group_id(raw):
    # Allow -100xxxx, or alias like MODELS_CHAT
    if raw.lstrip("-").isdigit():
        return int(raw)
    value = os.getenv(raw)
    if not value:
        raise ValueError(f"Group alias '{raw}' not found in environment variables.")
    return int(value)

jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

def register(app):

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")

        # Split command, expects at least 6 args
        # /scheduleflyer tipping 2025-07-16 12:23 once MODELS_CHAT
        args = message.text.split(maxsplit=5)
        if len(args) < 6:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group/alias>\n"
                "Example: /scheduleflyer tipping 2025-07-16 18:00 daily MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_raw = args[5]

        # Validate group ID or resolve alias
        try:
            group_id = resolve_group_id(group_raw)
        except Exception as e:
            return await message.reply(str(e))

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        tz = pytz.timezone(SCHED_TZ)
        # Combine date and time
        try:
            dt_str = f"{date_str} {time_str}"
            run_time = tz.localize(datetime.strptime(dt_str, "%Y-%m-%d %H:%M"))
        except Exception:
            return await message.reply("Invalid date/time format. Use YYYY-MM-DD and HH:MM.")

        async def post_flyer():
            try:
                if flyer.get("photo_id"):
                    await client.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
                else:
                    await client.send_message(group_id, flyer.get("caption", ""))
            except Exception as e:
                logging.error(f"Flyer schedule failed: {e}")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M')}"

        if repeat == "daily":
            scheduler.add_job(
                post_flyer,
                "cron",
                hour=run_time.hour,
                minute=run_time.minute,
                id=job_id,
                replace_existing=True,
                kwargs={},
            )
        else:  # once
            scheduler.add_job(
                post_flyer,
                "date",
                run_date=run_time,
                id=job_id,
                replace_existing=True,
                kwargs={},
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in {group_id} at {run_time.strftime('%Y-%m-%d %H:%M %Z')} ({repeat}).\nJob ID: <code>{job_id}</code>"
        )

    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No scheduled flyers.")
        lines = ["📅 Scheduled Flyers:"]
        for job in jobs:
            trigger = job.trigger
            lines.append(f"• {job.id} — {trigger}")
        await message.reply("\n".join(lines))

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancelflyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("No job found with that ID.")
        scheduler.remove_job(job_id)
        await message.reply(f"❌ Scheduled flyer <code>{job_id}</code> canceled.")

# --- register in main.py like: flyer_scheduler.register(app)
