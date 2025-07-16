import os
import logging
from datetime import datetime
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# --- CONFIG ---
MONGO_URI = os.getenv("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["flyer_db"]
flyers = db.flyers

SCHED_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

# --- ENV GROUP SHORTCUTS ---
GROUP_SHORTCUTS = {k: int(v) for k, v in os.environ.items() if k.endswith("_CHAT")}

# --- GLOBAL BOT CLIENT ---
BOT_CLIENT = None

def is_admin(user_id):
    return user_id in ADMINS

# --- JOB FUNCTION ---
async def post_flyer_job(group_id, flyer_name, chat_id):
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        logging.warning(f"Flyer '{flyer_name}' not found in chat {chat_id}")
        return
    if BOT_CLIENT is None:
        logging.error("BOT_CLIENT is not set!")
        return
    try:
        if flyer.get("photo_id"):
            await BOT_CLIENT.send_photo(group_id, flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await BOT_CLIENT.send_message(group_id, flyer.get("caption", ""))
        logging.info(f"Posted flyer '{flyer_name}' to {group_id}")
    except Exception as e:
        logging.error(f"Failed to post flyer '{flyer_name}': {e}")

# --- SCHEDULER SETUP ---
jobstore = {
    "default": MongoDBJobStore(client=mongo, database="flyer_db", collection="apscheduler_jobs")
}
scheduler = AsyncIOScheduler(jobstores=jobstore, timezone=pytz.timezone(SCHED_TZ))
scheduler.start()

def resolve_group_id(group_str):
    try:
        return int(group_str)
    except ValueError:
        return GROUP_SHORTCUTS.get(group_str.upper())

def register(app):
    global BOT_CLIENT
    BOT_CLIENT = app

    # --- Schedule a Flyer ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        # /scheduleflyer tipping 2025-07-16 15:30 once MODELS_CHAT
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can schedule flyers.")

        args = message.text.split()
        if len(args) < 6:
            return await message.reply(
                "Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group_id|GROUP_SHORTCUT>\n"
                "Example: /scheduleflyer tipping 2025-07-16 15:30 once MODELS_CHAT"
            )
        flyer_name = args[1].strip().lower()
        date_str = args[2]
        time_str = args[3]
        repeat = args[4].lower()
        group_str = args[5]
        group_id = resolve_group_id(group_str)
        if not group_id:
            return await message.reply("Invalid group_id or group shortcut!")

        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        try:
            sched_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            sched_dt = pytz.timezone(SCHED_TZ).localize(sched_dt)
        except Exception:
            return await message.reply("❌ Invalid date/time format. Use YYYY-MM-DD HH:MM (24h)")

        job_id = f"flyer_{flyer_name}_{group_id}_{sched_dt.strftime('%Y%m%d%H%M')}"

        if repeat == "daily":
            scheduler.add_job(
                post_flyer_job,
                "cron",
                hour=sched_dt.hour,
                minute=sched_dt.minute,
                id=job_id,
                args=[group_id, flyer_name, message.chat.id],
                replace_existing=True,
            )
        else:
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=sched_dt,
                id=job_id,
                args=[group_id, flyer_name, message.chat.id],
                replace_existing=True,
            )

        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to post in <code>{group_str}</code> at {sched_dt.strftime('%Y-%m-%d %H:%M')} ({'daily' if repeat == 'daily' else 'once'}).\nJob ID: <code>{job_id}</code>",
            parse_mode="HTML"
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
        await message.reply(f"❌ Scheduled flyer <code>{job_id}</code> canceled.", parse_mode="HTML")
