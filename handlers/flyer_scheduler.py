import logging
import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import sys

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
MAIN_LOOP = None  # Will be set by main.py

def log_debug(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[SCHEDULER][{ts}] {msg}"
    # Log to file
    try:
        with open("/tmp/scheduler_debug.log", "a") as f:
            f.write(msg + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}", file=sys.stderr)
    # Log to stdout
    print(msg, flush=True)

log_debug("flyer_scheduler.py module loaded!")

async def scheduleflyer_handler(client, message):
    log_debug(f"scheduleflyer_handler CALLED by user {message.from_user.id if message.from_user else 'unknown'}")
    args = message.text.split(maxsplit=4)
    log_debug(f"scheduleflyer_handler ARGS: {args}")
    if len(args) < 5:
        await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD HH:MM> <group>\n\n"
            "Example:\n/scheduleflyer tipping 2025-07-17 19:54 -1002884098395"
        )
        log_debug("scheduleflyer_handler: Not enough arguments!")
        return

    flyer_name = args[1]
    date_part = args[2]
    time_part = args[3]
    group = args[4]
    time_str = f"{date_part} {time_part}"

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await message.reply(f"❌ Invalid time format: {e}")
        log_debug(f"[ERROR] Invalid time format: {e}")
        return

    log_debug(f"Scheduling flyer '{flyer_name}' to group {group} at {post_time}")

    try:
        scheduler.add_job(
            func=run_post_flyer,
            trigger='date',
            run_date=post_time,
            args=[client, flyer_name, group]
        )
        log_debug(f"Job scheduled for flyer '{flyer_name}' in group {group} at {post_time}")
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {time_str} in {group}.")
    except Exception as e:
        log_debug(f"[ERROR] Could not schedule job: {e}")
        await message.reply(f"❌ Failed to schedule flyer: {e}")

async def post_flyer(client, flyer_name, group):
    log_debug(f"post_flyer CALLED with flyer_name={flyer_name}, group={group}")
    try:
        await client.send_message(group, f"📢 Scheduled Flyer: {flyer_name}")
        log_debug(f"SUCCESS! Flyer '{flyer_name}' posted to group {group}")
    except Exception as e:
        log_debug(f"[ERROR] Could not post flyer '{flyer_name}' to group {group}: {e}")

def run_post_flyer(client, flyer_name, group):
    log_debug(f"run_post_flyer CALLED for flyer_name={flyer_name}, group={group}")
    global MAIN_LOOP
    if MAIN_LOOP is None:
        try:
            MAIN_LOOP = asyncio.get_event_loop()
            log_debug("MAIN_LOOP was None, get_event_loop() succeeded")
        except Exception as e:
            log_debug(f"[ERROR] MAIN_LOOP get_event_loop failed: {e}")
    try:
        asyncio.run_coroutine_threadsafe(post_flyer(client, flyer_name, group), MAIN_LOOP)
        log_debug(f"Submitted post_flyer task to MAIN_LOOP for flyer '{flyer_name}' in group {group}")
    except Exception as e:
        log_debug(f"[ERROR] Failed to submit post_flyer to MAIN_LOOP: {e}")

def register(app):
    log_debug("register() CALLED")
    app.add_handler(
        MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")),
        group=0
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started in flyer_scheduler.")
        log_debug("Scheduler started in flyer_scheduler.")

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set from main.py")
