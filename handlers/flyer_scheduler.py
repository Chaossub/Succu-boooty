import os
import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pymongo import MongoClient
from pyrogram import filters, Client

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

def get_group_id_from_alias(alias):
    """Support for using environment shortcuts for group ids."""
    alias = alias.strip()
    # Allow numeric group id directly
    if alias.startswith('-'):
        try:
            return int(alias)
        except Exception:
            pass
    # Try environment
    val = os.getenv(alias.upper())
    if val:
        try:
            return int(val)
        except Exception:
            pass
    raise ValueError(f"Group alias '{alias}' not found in environment variables.")

# ---- JOB FUNC (must be import-level for serialization) ----
async def post_flyer_job(flyer_name, chat_id, group_id):
    app = Client("SuccuBot")  # or whatever you named your bot session!
    await app.start()
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        await app.send_message(group_id, f"❌ Flyer '{flyer_name}' not found for scheduled post.")
        await app.stop()
        return
    try:
        if flyer.get("photo_id"):
            await app.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await app.send_message(group_id, flyer.get("caption", ""))
    except Exception as e:
        logging.error(f"Flyer schedule failed: {e}")
    await app.stop()

# ---- MAIN HANDLER REGISTER ----
def register(app):
    # --- Schedule a Flyer ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_alias_or_id>\n"
                "Example: /scheduleflyer tipping 2025-07-18 18:00 daily MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_str = args[5]

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Group id/alias support
        try:
            group_id = get_group_id_from_alias(group_str)
        except Exception as e:
            return await message.reply(str(e))

        # Calculate run_time
        tz = pytz.timezone(SCHED_TZ)
        try:
            run_time = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
        except Exception:
            return await message.reply("Invalid date or time format. Use YYYY-MM-DD HH:MM.")

        now = datetime.now(tz)
        if run_time < now:
            return await message.reply("Scheduled time is in the past.")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M')}"

        # Schedule job using APScheduler (serialized by func name, not by passing objects!)
        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=run_time.hour,
                minute=run_time.minute,
                id=job_id,
                replace_existing=True,
                args=[flyer_name, message.chat.id, group_id],
            )
        else:  # once
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=run_time,
                id=job_id,
                replace_existing=True,
                args=[flyer_name, message.chat.id, group_id],
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in {group_id} at {run_time.strftime('%Y-%m-%d %H:%M')} ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>"
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
            if hasattr(trigger, "run_date"):
                when = trigger.run_date.strftime("%Y-%m-%d %H:%M")
            elif hasattr(trigger, "fields"):
                # For cron jobs
                when = f"daily at {trigger.fields[2].expressions[0]}:{trigger.fields[1].expressions[0]}"
            else:
                when = str(trigger)
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
