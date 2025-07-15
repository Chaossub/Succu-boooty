import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Example Mongo setup (adapt for your bot setup)
# from pymongo import MongoClient
# mongo_client = MongoClient(os.getenv("MONGO_URI"))
# flyer_jobs = mongo_client["your_db"]["flyer_jobs"]

logger = logging.getLogger("handlers.flyer_scheduler")

def send_scheduled_flyer(app, chat_id, flyer_name):
    # Your logic to send flyer goes here
    pass

def restore_jobs():
    jobs = list(flyer_jobs.find())
    logger.info(f"[restore_jobs] Found {len(jobs)} scheduled flyers in DB.")
    restored = 0
    for job in jobs:
        # Skip if required fields are missing
        for field in ("run_time", "chat_id", "flyer_name"):
            if field not in job:
                logger.warning(f"[restore_jobs] Skipping job {job.get('_id')} (missing {field}, probably old/corrupt)")
                break
        else:
            run_time = job["run_time"]
            try:
                # Try to parse both timezone-aware and naive datetimes
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
                    args=[app, job['chat_id'], job['flyer_name']],
                    id=str(job["_id"])
                )
                restored += 1
            except Exception as e:
                logger.error(f"[restore_jobs] Error adding job: {e}")
    logger.info(f"[restore_jobs] Restored {restored} scheduled flyer jobs.")

def register(app, scheduler):
    logger.info("Registering flyer_scheduler...")
    # your handler registrations here (add_message_handler etc)
    restore_jobs()
