import os
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters
from handlers.flyer import get_flyer_by_name
import pytz

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
scheduler.start()

app_instance = None  # Will be set by main.py on startup

def set_app_instance(app):
    global app_instance
    app_instance = app

# Helper: Get group id from environment variable or shortcut
def resolve_group_id(group_str):
    if group_str.startswith("-100"):
        return int(group_str)
    group_id = os.environ.get(group_str)
    if group_id:
        try:
            return int(group_id)
        except Exception as e:
            logger.error(f"Could not convert env {group_str}={group_id} to int: {e}")
            return None
    logger.error(f"Group alias '{group_str}' not found in environment variables.")
    return None

# The scheduled job
async def post_flyer_job(group_id, flyer_name, request_chat_id):
    logger.info(f"Running post_flyer_job: group_id={group_id}, flyer_name={flyer_name}")
    if app_instance is None:
        logger.error("app_instance is None in post_flyer_job! Cannot send flyer.")
        return
    flyer = get_flyer_by_name(group_id, flyer_name)
    if not flyer:
        logger.error(f"Flyer '{flyer_name}' not found for group {group_id}")
        await app_instance.send_message(
            chat_id=request_chat_id,
            text=f"❌ Flyer '{flyer_name}' not found for group {group_id}."
        )
        return
    file_id, caption = flyer
    try:
        await app_instance.send_photo(
            chat_id=group_id,
            photo=file_id,
            caption=caption or ""
        )
        logger.info(f"Posted flyer '{flyer_name}' to group {group_id}")
    except Exception as e:
        logger.error(f"Failed to post flyer: {e}")
        await app_instance.send_message(
            chat_id=request_chat_id,
            text=f"❌ Failed to post flyer: {e}"
        )

def register(app):
    set_app_instance(app)

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        logger.info(f"Got /scheduleflyer from {message.from_user.id} in {message.chat.id}: {message.text}")

        try:
            args = message.text.split()
            if len(args) < 5:
                return await message.reply("❌ Usage: <flyer> <YYYY-MM-DD> <HH:MM> <once/daily/weekly> <group>")

            flyer_name, date_str, time_str, repeat, group_str = args[1:6]

            group_id = resolve_group_id(group_str)
            if not group_id:
                return await message.reply(f"❌ Invalid group_id or group shortcut: {group_str}")

            tz_str = os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")
            try:
                tz = pytz.timezone(tz_str)
            except Exception:
                tz = pytz.timezone("America/Los_Angeles")

            try:
                dt = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
            except Exception as e:
                return await message.reply(f"❌ Invalid date/time format: {e}")

            job_id = f"flyer_{flyer_name}_{group_id}_{dt.strftime('%Y%m%d%H%M%S')}"
            logger.info(f"Scheduling flyer: {flyer_name} to {group_id} at {dt} | job_id={job_id}")

            # Remove existing job with same id, if any
            try:
                scheduler.remove_job(job_id)
            except Exception as e:
                logger.info(f"No existing job to remove for job_id={job_id}: {e}")

            scheduler.add_job(
                post_flyer_job,
                "date",
                run_date=dt,
                args=[group_id, flyer_name, message.chat.id],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300
            )

            await message.reply(
                f"✅ Scheduled flyer '{flyer_name}' to post in {group_str} at {dt} ({repeat}).\nJob ID: {job_id}"
            )
        except Exception as e:
            logger.error(f"Error scheduling flyer:\n{e}", exc_info=True)
            await message.reply(
                f"❌ Error: {e}"
            )
