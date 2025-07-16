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

SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")  # LA time!
OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

def is_admin(user_id):
    return user_id in ADMINS

# ---- APSCHEDULER ----
jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

def register(app):

    # --- Schedule a Flyer ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")
        args = message.text.split(maxsplit=4)
        if len(args) < 4:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <HH:MM> <once|daily> <group_id>\n"
                "Example: /scheduleflyer tipping 18:00 daily -1001234567890"
            )
        flyer_name = args[1].strip().lower()
        time_str = args[2]
        repeat = args[3].lower()
        group_id = int(args[4])

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Calculate first post time (today or tomorrow if time passed)
        now = datetime.now(pytz.timezone(SCHED_TZ))
        hour, minute = map(int, time_str.split(":"))
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)

        # --- JOB FUNC ---
        async def post_flyer():
            try:
                if flyer.get("photo_id"):
                    await client.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
                else:
                    await client.send_message(group_id, flyer.get("caption", ""))
            except Exception as e:
                logging.error(f"Flyer schedule failed: {e}")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M%S')}"

        if repeat == "daily":
            scheduler.add_job(
                post_flyer,
                "cron",
                hour=hour,
                minute=minute,
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
            f"✅ Scheduled flyer '{flyer_name}' to post in {group_id} at {time_str} ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>"
        )

    # --- List Scheduled Flyers ---
    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No scheduled flyers.")
        lines = ["📅 Scheduled Flyers:"]
        for job in jobs:
            trigger = job.trigger
            when = getattr(trigger, "run_date", None) or getattr(trigger, "fields", None)
            lines.append(f"• {job.id} — {when}")
        await message.reply("\n".join(lines))

    # --- Cancel Scheduled Flyer ---
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

# Remember to call scheduled_flyer.register(app) in your main.py

