import os
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import MongoClient
from pyrogram import filters

# Setup logging
logger = logging.getLogger("handlers.flyer_scheduler")
logging.basicConfig(level=logging.INFO)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")
mongo_client = MongoClient(MONGO_URI)
flyer_jobs = mongo_client[MONGO_DB]["flyer_jobs"]

def send_scheduled_flyer(app, chat_id, flyer_name):
    # Import flyer collection and sending logic
    from .flyer import get_flyer_by_name
    flyer = get_flyer_by_name(chat_id, flyer_name)
    if not flyer:
        logger.warning(f"[send_scheduled_flyer] Flyer '{flyer_name}' not found in chat {chat_id}")
        return
    try:
        app.send_photo(
            chat_id,
            flyer["file_id"],
            caption=flyer["caption"],
            parse_mode="HTML",
            disable_notification=True,
        )
        logger.info(f"[send_scheduled_flyer] Sent flyer '{flyer_name}' to chat {chat_id}")
    except Exception as e:
        logger.error(f"[send_scheduled_flyer] Failed to send flyer: {e}")

def restore_jobs(app, scheduler):
    jobs = list(flyer_jobs.find())
    logger.info(f"[restore_jobs] Found {len(jobs)} scheduled flyers in DB.")
    restored = 0
    for job in jobs:
        for field in ("run_time", "chat_id", "flyer_name"):
            if field not in job:
                logger.warning(f"[restore_jobs] Skipping job {job.get('_id')} (missing {field}, probably old/corrupt)")
                break
        else:
            run_time = job["run_time"]
            try:
                if "+" in run_time or "-" in run_time[10:]:
                    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
                else:
                    dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.error(f"[restore_jobs] Error restoring job: {e}")
                continue
            try:
                scheduler.add_job(
                    send_scheduled_flyer,
                    trigger="date",
                    run_date=dt,
                    args=[app, job["chat_id"], job["flyer_name"]],
                    id=str(job["_id"]),
                )
                restored += 1
            except Exception as e:
                logger.error(f"[restore_jobs] Error adding job: {e}")
    logger.info(f"[restore_jobs] Restored {restored} scheduled flyer jobs.")

def schedule_flyer_handler(app, message):
    # /scheduleflyer <flyer_name> <target_chat_id> <YYYY-MM-DD HH:MM:SS>
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        return message.reply("Usage: /scheduleflyer <flyer_name> <target_chat_id> <YYYY-MM-DD HH:MM:SS>")
    flyer_name, target_chat_id, run_time = args[1], int(args[2]), args[3]
    # You may want to add more validation here
    flyer_jobs.insert_one({
        "chat_id": target_chat_id,
        "flyer_name": flyer_name,
        "run_time": run_time,
    })
    scheduler = app.scheduler if hasattr(app, "scheduler") else AsyncIOScheduler()
    try:
        if "+" in run_time or "-" in run_time[10:]:
            dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S%z")
        else:
            dt = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return message.reply("❌ Invalid datetime format! Use YYYY-MM-DD HH:MM:SS")
    scheduler.add_job(
        send_scheduled_flyer,
        trigger="date",
        run_date=dt,
        args=[app, target_chat_id, flyer_name],
        id=f"{flyer_name}_{target_chat_id}_{int(dt.timestamp())}"
    )
    message.reply(f"✅ Scheduled flyer '{flyer_name}' to {target_chat_id} at {run_time}")

def register(app, scheduler):
    logger.info("Registering flyer_scheduler...")
    app.add_handler(filters.command("scheduleflyer")(lambda c, m: schedule_flyer_handler(app, m)))
    restore_jobs(app, scheduler)

