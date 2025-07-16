import os
import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.jobstores.base import JobLookupError
from pyrogram import filters
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

# ---- APSCHEDULER ----
jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

# --- Group shortcut resolution ---
def resolve_group_id(group_str):
    # If user types a shortcut, resolve from environment (MODELS_CHAT, SUCCUBUS_SANCTUARY, etc)
    if group_str.startswith("-"):
        return int(group_str)
    env_id = os.getenv(group_str.upper())
    if env_id:
        return int(env_id)
    raise ValueError(f"Invalid group_id or group shortcut: {group_str}")

# --- Flyer Posting Job (must be top-level function for APScheduler!) ---
async def post_flyer_job(group_id, flyer_name, origin_chat_id):
    flyer = flyers.find_one({"chat_id": origin_chat_id, "name": flyer_name})
    from pyrogram import Client  # Safe import inside function
    app = Client.current
    if not flyer:
        logging.error(f"Flyer '{flyer_name}' not found in chat {origin_chat_id}")
        return
    try:
        if flyer.get("photo_id"):
            await app.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await app.send_message(group_id, flyer.get("caption", ""))
    except Exception as e:
        logging.error(f"Flyer schedule failed: {e}")

def register(app):
    # --- Schedule a Flyer ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")
        args = message.text.split()
        if len(args) < 6:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_id or shortcut>\n"
                "Example: /scheduleflyer tipping 2025-07-16 18:00 once MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_str = args[5]

        try:
            group_id = resolve_group_id(group_str)
        except Exception as e:
            return await message.reply(str(e))

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Schedule datetime (timezone aware)
        sched_dt = pytz.timezone(SCHED_TZ).localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))

        job_id = f"flyer_{flyer_name}_{group_id}_{sched_dt.strftime('%Y%m%d%H%M')}"

        # Remove any duplicate jobs with this id
        try:
            scheduler.remove_job(job_id)
        except JobLookupError:
            pass

        # APScheduler only allows top-level callables, so use our global async def post_flyer_job!
        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=sched_dt.hour,
                minute=sched_dt.minute,
                args=[group_id, flyer_name, message.chat.id],
                id=job_id,
                replace_existing=True,
            )
        else:  # once
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=sched_dt,
                args=[group_id, flyer_name, message.chat.id],
                id=job_id,
                replace_existing=True,
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in <code>{group_str}</code> at {sched_dt.strftime('%Y-%m-%d %H:%M')} ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>"
        )

    # --- List Scheduled Flyers ---
    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message):
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
    async def cancelflyer_handler(client, message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("No job found with that ID.")
        scheduler.remove_job(job_id)
        await message.reply(f"❌ Scheduled flyer <code>{job_id}</code> canceled.")
