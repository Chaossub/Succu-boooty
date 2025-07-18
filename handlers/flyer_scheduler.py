import os
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters
import pytz
from handlers.flyer import get_flyer_by_name

# --- Scheduler Setup ---
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
scheduler.start()

# Global reference to running app, set in register()
app_ref = None

# --- Admin & Owner ID ---
OWNER_ID = 6964994611  # << Your Telegram ID

def is_admin(app, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"Admin check failed: {e}")
        return False

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

async def post_flyer_job(group_id, flyer_name, request_chat_id=None):
    app = app_ref
    logger.info(f"Running post_flyer_job: group_id={group_id}, flyer_name={flyer_name}")
    flyer = get_flyer_by_name(group_id, flyer_name)
    if not flyer:
        logger.error(f"Flyer '{flyer_name}' not found for group {group_id}")
        if request_chat_id:
            await app.send_message(
                chat_id=request_chat_id,
                text=f"❌ Flyer '{flyer_name}' not found for group <code>{group_id}</code>.",
            )
        return
    file_id, caption = flyer
    try:
        await app.send_photo(
            chat_id=group_id,
            photo=file_id,
            caption=caption or ""
        )
        logger.info(f"Posted flyer '{flyer_name}' to group {group_id}")
    except Exception as e:
        logger.error(f"Failed to post flyer: {e}")
        if request_chat_id:
            await app.send_message(
                chat_id=request_chat_id,
                text=f"❌ Failed to post flyer: {e}"
            )

def register(app):
    global app_ref
    app_ref = app

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        logger.info(f"Got /scheduleflyer from {message.from_user.id} in {message.chat.id}: {message.text}")

        # Admin/Owner check
        if not is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")

        try:
            args = message.text.split()
            if len(args) < 6:
                return await message.reply(
                    "❌ Usage: <flyer> <YYYY-MM-DD> <HH:MM> <once/daily/weekly> <group>",
                )
            flyer_name, date_str, time_str, repeat, group_str = args[1:6]

            group_id = resolve_group_id(group_str)
            if not group_id:
                return await message.reply(f"❌ Invalid group_id or shortcut: {group_str}")

            # Use LA time by default or env override
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

            # Add the job (only ONCE for now)
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
                f"✅ Scheduled flyer '<b>{flyer_name}</b>' to post in <code>{group_str}</code> at <b>{dt}</b> ({repeat}).\nJob ID: <code>{job_id}</code>"
            )
        except Exception as e:
            logger.error(f"Error scheduling flyer:\n{e}", exc_info=True)
            await message.reply(
                f"❌ Error: {e}"
            )
