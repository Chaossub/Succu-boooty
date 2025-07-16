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

# --- Helper to resolve group aliases ---
def resolve_group(group_str):
    if group_str.lstrip("-").isdigit():
        return int(group_str)
    # Check env vars (upper, _ID, etc)
    val = os.getenv(group_str)
    if val and val.lstrip("-").isdigit():
        return int(val)
    # If not found, try with _ID suffix
    val = os.getenv(group_str.upper() + "_ID")
    if val and val.lstrip("-").isdigit():
        return int(val)
    raise ValueError(f"Group alias '{group_str}' not found in environment variables.")

# --- The actual job to post flyers ---
async def post_flyer_job(client, group_id, flyer_name, chat_id):
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        logging.error(f"Flyer '{flyer_name}' not found in chat {chat_id}")
        return
    try:
        if flyer.get("photo_id"):
            await client.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await client.send_message(group_id, flyer.get("caption", ""))
    except Exception as e:
        logging.error(f"Flyer schedule failed: {e}")

def register(app):
    # --- Schedule a Flyer ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        args = message.text.split(maxsplit=5)
        if len(args) < 6:
            return await message.reply(
                "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_alias_or_id>\n"
                "Example: /scheduleflyer tipping 2025-07-18 18:00 daily MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_str = args[5]

        # Validate flyer exists
        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Parse group/alias
        try:
            group_id = resolve_group(group_str)
        except Exception as e:
            return await message.reply(str(e))

        # Parse date/time
        try:
            run_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            run_date = pytz.timezone(SCHED_TZ).localize(run_date)
        except Exception as e:
            return await message.reply("❌ Invalid date/time format. Use YYYY-MM-DD and HH:MM (24h).")

        # If one-time and time is past, error
        now = datetime.now(pytz.timezone(SCHED_TZ))
        if run_date < now and repeat == "once":
            return await message.reply("❌ That date/time is in the past!")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_date.strftime('%Y%m%d%H%M')}_{repeat}"

        # Schedule job
        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=run_date.hour,
                minute=run_date.minute,
                args=[client, group_id, flyer_name, message.chat.id],
                id=job_id,
                replace_existing=True,
            )
        else:  # once
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=run_date,
                args=[client, group_id, flyer_name, message.chat.id],
                id=job_id,
                replace_existing=True,
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in <code>{group_str}</code> at <b>{date_str} {time_str}</b> ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>",
            parse_mode="html"
        )

    # --- List Scheduled Flyers ---
    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No scheduled flyers.")
        lines = ["📅 Scheduled Flyers:"]
        for job in jobs:
            lines.append(f"• {job.id} — Next run: {job.next_run_time}")
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
        await message.reply(f"❌ Scheduled flyer <code>{job_id}</code> canceled.", parse_mode="html")
