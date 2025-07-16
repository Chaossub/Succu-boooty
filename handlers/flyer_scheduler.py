import os
import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pyrogram import Client
from pymongo import MongoClient
from pyrogram.errors import RPCError

# ---- CONFIG ----
MONGO_URI = os.getenv("MONGO_URI")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

mongo = MongoClient(MONGO_URI)
db = mongo["flyer_db"]
flyers = db.flyers

SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

def is_admin(user_id):
    return user_id in ADMINS

jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

# --- APSCHEDULER-SAFE: top-level, no client arg ---
def post_flyer_job(group_id, flyer_name, source_chat_id):
    """Standalone scheduled flyer post (runs in background via scheduler)."""
    # Create a new client for each job
    api_id = int(os.environ["API_ID"])
    api_hash = os.environ["API_HASH"]
    bot_token = os.environ["BOT_TOKEN"]
    flyer_db_uri = os.environ["MONGO_URI"]

    mongo = MongoClient(flyer_db_uri)
    db = mongo["flyer_db"]
    flyers = db.flyers

    flyer = flyers.find_one({"chat_id": source_chat_id, "name": flyer_name})
    if not flyer:
        logging.error(f"Flyer '{flyer_name}' not found for scheduled post.")
        return

    # Start a new pyrogram client just for this job
    app = Client("scheduler_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, parse_mode="html")
    async def runner():
        async with app:
            try:
                if flyer.get("photo_id"):
                    await app.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
                else:
                    await app.send_message(group_id, flyer.get("caption", ""))
                logging.info(f"Sent scheduled flyer '{flyer_name}' to {group_id}")
            except RPCError as e:
                logging.error(f"Failed to send flyer: {e}")
    import asyncio
    asyncio.run(runner())

def register(app):
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")

        # <name> <YYYY-MM-DD> <HH:MM> <once|daily> <alias|id>
        args = message.text.split(maxsplit=5)
        if len(args) < 6:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_id or ALIAS>\n"
                "Example: /scheduleflyer tipping 2025-07-17 18:00 daily MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_key = args[5]

        # Parse group id or alias
        if group_key.startswith("-"):
            group_id = int(group_key)
        else:
            group_id_env = os.getenv(group_key)
            if not group_id_env:
                return await message.reply(f"Group alias '{group_key}' not found in environment variables.")
            group_id = int(group_id_env)

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        # Parse date/time
        try:
            dt_str = f"{date_str} {time_str}"
            run_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            tz = pytz.timezone(SCHED_TZ)
            run_time = tz.localize(run_time)
        except Exception as e:
            return await message.reply(f"❌ Could not parse date/time: {e}")

        hour = run_time.hour
        minute = run_time.minute

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M%S')}"

        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True,
                args=[group_id, flyer_name, message.chat.id]
            )
        else:  # once
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=run_time,
                id=job_id,
                replace_existing=True,
                args=[group_id, flyer_name, message.chat.id]
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in {group_id} at {run_time.strftime('%Y-%m-%d %H:%M')} ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>"
        )

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
