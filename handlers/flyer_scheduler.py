import os
import logging
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Environment variables
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME", "Succubot")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")

GROUP_ENV_MAP = {
    "MODELS_CHAT": os.getenv("MODELS_CHAT"),
    "SUCCUBUS_SANCTUARY": os.getenv("SUCCUBUS_SANCTUARY"),
    # Add others as needed
}

# Pyrogram client (ensure only ONE session for all bot work!)
app = Client(
    "Succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# MongoDB flyer storage
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers

# Scheduler
scheduler = AsyncIOScheduler(timezone=SCHED_TZ)
scheduler.start()

def group_name_to_id(name):
    return int(GROUP_ENV_MAP.get(name) or name)

async def post_flyer_job(group_id, flyer_name):
    logger.info(f"Running post_flyer_job: group_id={group_id}, flyer_name={flyer_name}")
    try:
        # Ensure chat is "warmed up" in session (avoids Peer id invalid)
        await app.get_chat(group_id)
    except Exception as e:
        logger.warning(f"Could not preload group {group_id}: {e}")

    flyer = flyers.find_one({"group_id": group_id, "name": flyer_name})
    if not flyer:
        logger.error(f"Flyer '{flyer_name}' not found for group {group_id}")
        return

    try:
        if flyer.get("file_id"):
            await app.send_photo(
                group_id,
                flyer["file_id"],
                caption=flyer.get("caption", "")
            )
        elif flyer.get("text"):
            await app.send_message(
                group_id,
                flyer["text"]
            )
        else:
            logger.error(f"Flyer '{flyer_name}' has no content for group {group_id}")
            return
        logger.info(f"✅ Flyer '{flyer_name}' posted to {group_id}")
    except PeerIdInvalid:
        logger.error(f"Failed to post flyer: Peer id invalid: {group_id}")
    except Exception as e:
        logger.error(f"Failed to post flyer: {e}")

async def scheduleflyer_handler(client, message):
    # Parse: /scheduleflyer flyername YYYY-MM-DD HH:MM [once|daily|weekly] GROUP_ENV
    try:
        parts = message.text.strip().split()
        if len(parts) < 6:
            await message.reply("❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily|weekly> <GROUP_ENV>")
            return
        _, flyer_name, date_str, time_str, repeat, group_env = parts[:6]
        group_id = group_name_to_id(group_env)
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        local_tz = pytz.timezone(SCHED_TZ)
        dt = local_tz.localize(dt)

        job_id = f"flyer_{flyer_name}_{group_id}_{dt.strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Scheduling flyer: {flyer_name} to {group_id} at {dt} | job_id={job_id}")

        # Remove old job if exists
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

        if repeat == "once":
            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=dt,
                args=[group_id, flyer_name],
                id=job_id
            )
            await message.reply(
                f"✅ Scheduled flyer '{flyer_name}' to post in <b>{group_env}</b> at <b>{dt}</b> (once).\nJob ID: <code>{job_id}</code>",
                parse_mode="html"
            )
        else:
            await message.reply("❌ Only 'once' scheduling is implemented in this version.")

    except Exception as e:
        logger.error(f"Error scheduling flyer:\n{e}")
        await message.reply(f"❌ Failed to schedule flyer: {e}")

def register(app):
    # Register scheduler commands
    from pyrogram import filters

    @app.on_message(filters.command("scheduleflyer") & filters.user([int(os.getenv("OWNER_ID", "6964994611"))]))
    async def wrapped_scheduleflyer_handler(client, message):
        await scheduleflyer_handler(client, message)

# Register at import (if main or from main.py)
register(app)
