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

# GROUP ALIAS SUPPORT
ALIASES = {
    "MODELS_CHAT": int(os.environ.get("MODELS_CHAT", "-1002884098395")),
    "SUCCUBUS_SANCTUARY": int(os.environ.get("SUCCUBUS_SANCTUARY", "-1002823762054")),
}

def is_admin(user_id):
    return user_id in ADMINS

# ---- APSCHEDULER ----
jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

def resolve_group(arg):
    # allow numeric ID or alias
    if arg.isdigit() or (arg.startswith("-100") and arg[1:].isdigit()):
        return int(arg)
    if arg in ALIASES:
        return ALIASES[arg]
    raise ValueError(f"Group alias '{arg}' not found in environment variables.")

def register(app):
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")

        args = message.text.split()
        # Flexible: allow either date+time or just time
        if len(args) == 6:  # /scheduleflyer <flyer> <YYYY-MM-DD> <HH:MM> <once|daily> <group>
            flyer_name, date_str, time_str, repeat, group_arg = args[1], args[2], args[3], args[4], args[5]
            date_part = date_str
        elif len(args) == 5:  # /scheduleflyer <flyer> <HH:MM> <once|daily> <group>
            flyer_name, time_str, repeat, group_arg = args[1], args[2], args[3], args[4]
            date_part = None
        else:
            return await message.reply(
                "Usage:\n"
                "  /scheduleflyer <flyer_name> <HH:MM> <once|daily> <group>\n"
                "  /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group>\n"
                "Group can be chat ID or alias (MODELS_CHAT, etc.)"
            )

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name.lower()})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        try:
            group_id = resolve_group(group_arg)
        except Exception as e:
            return await message.reply(str(e))

        now = datetime.now(pytz.timezone(SCHED_TZ))
        if date_part:
            try:
                day = datetime.strptime(date_part, "%Y-%m-%d").date()
            except Exception:
                return await message.reply("Date must be YYYY-MM-DD")
            hour, minute = map(int, time_str.split(":"))
            run_time = pytz.timezone(SCHED_TZ).localize(datetime.combine(day, datetime.min.time()))
            run_time = run_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            hour, minute = map(int, time_str.split(":"))
            run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_time < now:
                run_time += timedelta(days=1)

        async def post_flyer():
            try:
                if flyer.get("photo_id"):
                    await client.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
                else:
                    await client.send_message(group_id, flyer.get("caption", ""))
            except Exception as e:
                logging.error(f"Flyer schedule failed: {e}")

        job_id = f"flyer_{flyer_name}_{group_id}_{run_time.strftime('%Y%m%d%H%M%S')}"
        if repeat.lower() == "daily":
            scheduler.add_job(
                post_flyer,
                "cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True,
            )
        else:
            scheduler.add_job(
                post_flyer,
                "date",
                run_date=run_time,
                id=job_id,
                replace_existing=True,
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in {group_arg} at {run_time.strftime('%Y-%m-%d %H:%M')} ({'daily' if repeat=='daily' else 'once'}).\nJob ID: <code>{job_id}</code>"
        )
