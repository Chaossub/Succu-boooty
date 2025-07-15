import os
import logging
from datetime import datetime, timedelta
import pytz

from pyrogram import filters
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Setup logger for this module
logger = logging.getLogger(__name__)

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers
scheduled = db.scheduled_flyers

ADMIN_IDS = [6964994611]  # <-- YOUR ADMIN ID
ALIASES = {
    "MODELS_CHAT": int(os.environ["MODELS_CHAT"]),
    "SUCCUBUS_SANCTUARY": int(os.environ["SUCCUBUS_SANCTUARY"]),
    "TEST_GROUP": int(os.environ["TEST_GROUP"]),
}
DEFAULT_TZ = os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")

def admin_filter(_, __, m):
    return m.from_user and m.from_user.id in ADMIN_IDS

async def send_flyer_job(app, chat_id, flyer_name):
    flyer = flyers.find_one({"name": flyer_name})
    if flyer:
        try:
            if flyer.get("file_id"):
                await app.send_photo(chat_id, flyer["file_id"], caption=flyer.get("caption", ""))
            else:
                await app.send_message(chat_id, flyer.get("caption", ""))
        except Exception as e:
            logger.exception(f"[send_flyer_job] Failed to send flyer '{flyer_name}' to {chat_id}: {e}")

def restore_jobs(scheduler, app):
    jobs = list(scheduled.find({}))
    logger.info(f"[restore_jobs] Found {len(jobs)} scheduled flyers in DB.")
    for job in jobs:
        try:
            run_time = job.get("run_time")
            if not run_time:
                logger.warning(f"[restore_jobs] Skipping job {job.get('_id')} (missing run_time, probably old/corrupt)")
                continue
            # Try with tz-aware string first, else fallback to naive
            try:
                parsed = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
            except ValueError:
                parsed = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
                parsed = pytz.timezone(DEFAULT_TZ).localize(parsed)
            scheduler.add_job(
                send_flyer_job,
                trigger="date",
                run_date=parsed,
                args=[app, job['chat_id'], job['flyer_name']],
                id=str(job["_id"])
            )
            logger.info(f"Restored job for flyer '{job['flyer_name']}' at {parsed} to chat {job['chat_id']}")
        except Exception as e:
            logger.exception(f"[restore_jobs] Error restoring job: {e}")

def register(app, scheduler):
    logger.info("Registering flyer_scheduler...")

    @app.on_message(filters.command("scheduleflyer") & filters.create(admin_filter))
    async def scheduleflyer_handler(client, message):
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <group_alias> <HH:MM>")
        flyer_name, group_alias, time_str = args[1:4]
        group_id = ALIASES.get(group_alias)
        if not group_id:
            return await message.reply("❌ Invalid group/alias.")
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        now = datetime.now(pytz.timezone(DEFAULT_TZ))
        hour, minute = map(int, time_str.split(":"))
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        run_time_str = run_time.strftime("%Y-%m-%d %H:%M:%S%z")
        job_id = scheduled.insert_one({
            "flyer_name": flyer_name,
            "chat_id": group_id,
            "run_time": run_time_str
        }).inserted_id
        scheduler.add_job(
            send_flyer_job,
            trigger="date",
            run_date=run_time,
            args=[app, group_id, flyer_name],
            id=str(job_id)
        )
        await message.reply(
            f"✅ Scheduled flyer '{flyer_name}' to {group_alias} at {run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\nJob ID: <code>{job_id}</code>"
        )

    @app.on_message(filters.command("listscheduled") & filters.create(admin_filter))
    async def list_scheduled(client, message):
        jobs = list(scheduled.find({}))
        if not jobs:
            await message.reply("No flyers scheduled.")
        else:
            lines = [
                f"• <b>{j['flyer_name']}</b> to {j['chat_id']} at {j['run_time']} [job_id: <code>{j['_id']}</code>]"
                for j in jobs
            ]
            await message.reply("Scheduled Flyers:\n" + "\n".join(lines))

    @app.on_message(filters.command("cancelflyer") & filters.create(admin_filter))
    async def cancelflyer(client, message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        try:
            scheduler.remove_job(job_id)
            scheduled.delete_one({"_id": job_id})
            await message.reply("✅ Scheduled flyer canceled.")
        except Exception as e:
            await message.reply(f"❌ Could not cancel: {e}")

    # Restore jobs on startup
    restore_jobs(scheduler, app)
    logger.info("Restored scheduled flyer jobs.")
