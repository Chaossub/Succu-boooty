import logging
from datetime import datetime
from pyrogram.filters import command
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pymongo import MongoClient
import pytz
import os

mongo_client = MongoClient(os.environ["MONGO_URI"])
db = mongo_client[os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")]
flyers = db.flyers
scheduled = db.scheduled_flyers

logger = logging.getLogger(__name__)

def restore_jobs(scheduler, app):
    jobs = list(scheduled.find({}))
    logger.info(f"[restore_jobs] Found {len(jobs)} scheduled flyers in DB.")
    for job in jobs:
        try:
            # Recover timezone-aware time
            run_time = job.get("run_time")
            if not run_time:
                logger.warning(f"[restore_jobs] Skipping job {job['_id']} (missing run_time, probably old/corrupt)")
                continue
            run_time = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
            scheduler.add_job(
                send_flyer_job,
                trigger="date",
                run_date=run_time,
                args=[app, job['chat_id'], job['flyer_name']],
                id=job["_id"]
            )
            logger.info(f"Restored job for flyer '{job['flyer_name']}' at {run_time} to chat {job['chat_id']}")
        except Exception as e:
            logger.exception(f"[restore_jobs] Error restoring job: {e}")

async def send_flyer_job(app, chat_id, flyer_name):
    flyer = flyers.find_one({"name": flyer_name})
    if not flyer:
        logger.warning(f"Flyer '{flyer_name}' not found in DB for scheduled post!")
        return
    try:
        await app.send_photo(
            chat_id=chat_id,
            photo=flyer["file_id"],
            caption=flyer.get("caption", "")
        )
    except Exception as e:
        logger.error(f"Failed to send scheduled flyer '{flyer_name}' to {chat_id}: {e}")

def register(app, scheduler):
    logging.info("Registering flyer_scheduler...")

    @app.on_message(command("scheduleflyer"))
    async def scheduleflyer_handler(client, message: Message):
        # Usage: /scheduleflyer flyername CHAT_ALIAS/ID YYYY-MM-DD HH:MM
        try:
            args = message.text.split(maxsplit=4)
            if len(args) < 5:
                return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <CHAT> <YYYY-MM-DD> <HH:MM>")
            flyer_name = args[1]
            chat = args[2]
            date_str = args[3]
            time_str = args[4]

            # Chat alias resolving (support for MODELS_CHAT env alias)
            chat_id = os.environ.get(chat) or chat
            try:
                chat_id = int(chat_id)
            except ValueError:
                return await message.reply("❌ Invalid chat ID or alias.")

            # Compose timezone-aware datetime
            tz = pytz.timezone(os.environ.get("SCHEDULER_TZ", "America/Los_Angeles"))
            run_time = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))

            # Confirm flyer exists
            flyer = flyers.find_one({"name": flyer_name})
            if not flyer:
                return await message.reply(f"❌ Flyer '{flyer_name}' not found.")

            # Save scheduled job to DB
            job_id = f"flyer_{flyer_name}_{chat_id}_{int(run_time.timestamp())}"
            scheduled.insert_one({
                "_id": job_id,
                "chat_id": chat_id,
                "flyer_name": flyer_name,
                "run_time": run_time.strftime("%Y-%m-%d %H:%M:%S%z"),
            })

            # Schedule with APScheduler
            scheduler.add_job(
                send_flyer_job,
                trigger="date",
                run_date=run_time,
                args=[app, chat_id, flyer_name],
                id=job_id
            )

            await message.reply(
                f"✅ Scheduled flyer '{flyer_name}' to {chat} at {date_str} {time_str}.\nJob ID: <code>{job_id}</code>",
                quote=True
            )
        except Exception as e:
            logger.exception("Failed to schedule flyer!")
            await message.reply(f"❌ Error scheduling flyer: {e}")

    # Restore jobs at startup
    restore_jobs(scheduler, app)
    logging.info("Restored scheduled flyer jobs.")
