import os
import logging
import asyncio
from datetime import datetime, time as dt_time, timedelta
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message

# --- Setup logging ---
logger = logging.getLogger("handlers.flyer_scheduler")
logger.setLevel(logging.INFO)

# --- MongoDB Setup ---
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers
scheduled = db.scheduled_flyers

# --- Group Aliases ---
GROUP_ALIASES = {
    "MODELS_CHAT": -1002884098395,
    "SUCCUBUS_SANCTUARY": -1002823762054,
    "TEST_GROUP": -1002813378700,
}
def resolve_group(alias_or_id):
    if isinstance(alias_or_id, int):
        return alias_or_id
    if str(alias_or_id).isdigit():
        return int(alias_or_id)
    return GROUP_ALIASES.get(alias_or_id.upper())

# --- Helper: Post flyer to group (text or photo) ---
async def post_flyer(app, flyer, group_id):
    try:
        logger.info(f"Posting flyer: {flyer.get('name')} to {group_id}")
        if flyer.get("file_id"):
            await app.send_photo(
                group_id,
                flyer["file_id"],
                caption=flyer.get("caption") or flyer.get("text", "")
            )
        else:
            await app.send_message(
                group_id,
                flyer.get("text") or flyer.get("caption", "")
            )
        logger.info(f"Posted flyer {flyer.get('name')} to {group_id}")
    except Exception as e:
        logger.error(f"Failed scheduled flyer post: {e}")

# --- Scheduler Job ---
def flyer_job(app, flyer_name, group_id):
    flyer = flyers.find_one({"name": flyer_name})
    if not flyer:
        logger.error(f"Flyer '{flyer_name}' not found in DB.")
        return
    # Must run async method from sync APScheduler thread
    asyncio.run(post_flyer(app, flyer, group_id))

# --- Register flyer scheduler commands ---
def register(app, scheduler):
    @app.on_message(filters.command("scheduleflyer") & filters.user(6964994611))
    async def scheduleflyer_handler(client: Client, message: Message):
        # Usage: /scheduleflyer <flyer_name> <HH:MM> <group_alias>
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <HH:MM> <group>")
        flyer_name, time_str, group_alias = parts[1], parts[2], parts[3]
        group_id = resolve_group(group_alias)
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        try:
            hour, minute = map(int, time_str.split(":"))
            now = datetime.now()
            run_dt = datetime.combine(now.date(), dt_time(hour, minute))
            if run_dt < now:
                run_dt += timedelta(days=1)
            # Unique job id
            job_id = f"flyer_{flyer_name}_{group_id}_{run_dt.timestamp()}"
            # Schedule job
            scheduler.add_job(
                lambda: flyer_job(app, flyer_name, group_id),
                "date",
                run_date=run_dt,
                id=job_id,
                replace_existing=True
            )
            scheduled.insert_one({
                "name": flyer_name,
                "group": group_id,
                "time": time_str,
                "freq": "once",
                "job_id": job_id,
                "run_at": run_dt.isoformat(),
            })
            await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {group_alias} at {time_str}.")
        except Exception as e:
            logger.error(f"Failed to schedule flyer: {e}")
            await message.reply(f"❌ Error: {e}")

    @app.on_message(filters.command("listscheduled") & filters.user(6964994611))
    async def list_scheduled(client: Client, message: Message):
        jobs = list(scheduled.find())
        if not jobs:
            return await message.reply("No scheduled flyers.")
        txt = "Scheduled Flyers:\n" + "\n".join(
            f"- {j['name']} to {j['group']} at {j['time']} ({j['freq']}) [job_id: {j['job_id']}]" for j in jobs
        )
        await message.reply(txt)

    @app.on_message(filters.command("cancelflyer") & filters.user(6964994611))
    async def cancel_scheduled(client: Client, message: Message):
        # Usage: /cancelflyer <job_id>
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = parts[1].strip()
        try:
            scheduler.remove_job(job_id)
            scheduled.delete_one({"job_id": job_id})
            await message.reply(f"✅ Cancelled scheduled flyer with job_id: {job_id}")
        except Exception as e:
            logger.error(f"Error cancelling flyer job {job_id}: {e}")
            await message.reply(f"❌ Error cancelling flyer: {e}")

# --- To use: in main.py ---
# from handlers import flyer_scheduler
# flyer_scheduler.register(app, scheduler)
