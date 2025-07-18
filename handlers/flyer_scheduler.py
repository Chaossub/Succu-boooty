import logging 
import asyncio
import os
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import sys
from pymongo import MongoClient

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
MAIN_LOOP = None  # Will be set by main.py

# Mongo
mongo_uri = os.getenv("MONGO_URI")
mongo_db = os.getenv("MONGO_DBNAME")
flyer_client = MongoClient(mongo_uri)[mongo_db]
flyer_collection = flyer_client["flyers"]

MAX_CAPTION_LENGTH = 1024
OWNER_ID = 6964994611

# NEW: Track jobs for cancellation
SCHEDULED_FLYER_JOBS = {}  # (flyer_name, group) -> job

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

def resolve_group_name(group):
    if group.startswith('-') or group.startswith('@'):
        return group
    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()
    return group

log_debug("flyer_scheduler.py module loaded!")

async def scheduleflyer_handler(client, message):
    log_debug(f"scheduleflyer_handler CALLED by user {message.from_user.id if message.from_user else 'unknown'}")
    if message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can schedule flyers.")
        return
    args = message.text.split(maxsplit=4)
    log_debug(f"scheduleflyer_handler ARGS: {args}")
    if len(args) < 5:
        await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD HH:MM> <group>\n\n"
            "Example:\n/scheduleflyer tipping 2025-07-17 19:54 MODELS_CHAT"
        )
        log_debug("scheduleflyer_handler: Not enough arguments!")
        return

    flyer_name = args[1]
    date_part = args[2]
    time_part = args[3]
    group = resolve_group_name(args[4])
    time_str = f"{date_part} {time_part}"

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await message.reply(f"❌ Invalid time format: {e}")
        log_debug(f"[ERROR] Invalid time format: {e}")
        return

    try:
        await client.get_chat(group)
        log_debug(f"client.get_chat({group}) succeeded before scheduling.")
    except Exception as e:
        log_debug(f"[ERROR] client.get_chat({group}) failed: {e}")

    log_debug(f"Scheduling flyer '{flyer_name}' to group {group} at {post_time}")

    try:
        job = scheduler.add_job(
            func=run_post_flyer,
            trigger='date',
            run_date=post_time,
            args=[client, flyer_name, group]
        )
        # Track job for cancellation
        SCHEDULED_FLYER_JOBS[(flyer_name, group)] = job
        log_debug(f"Job scheduled for flyer '{flyer_name}' in group {group} at {post_time}")
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {time_str} in {group}.")
    except Exception as e:
        log_debug(f"[ERROR] Could not schedule job: {e}")
        await message.reply(f"❌ Failed to schedule flyer: {e}")

async def post_flyer(client, flyer_name, group):
    log_debug(f"post_flyer CALLED with flyer_name={flyer_name}, group={group}")
    flyer = flyer_collection.find_one({"name": flyer_name})
    log_debug(f"Loaded flyer from DB: {flyer}")
    if not flyer:
        log_debug(f"[ERROR] Flyer '{flyer_name}' not found in DB.")
        await client.send_message(group, f"❌ Flyer '{flyer_name}' not found.")
        return

    try:
        caption = flyer.get("caption", "")
        file_id = flyer.get("file_id")  # Always use 'file_id'!
        if file_id and isinstance(file_id, str) and file_id.strip():
            # Ensure caption does not exceed Telegram's max length
            send_caption = caption[:MAX_CAPTION_LENGTH] if len(caption) > MAX_CAPTION_LENGTH else caption
            await client.send_photo(group, file_id, caption=send_caption)
            log_debug(f"SUCCESS! Flyer '{flyer_name}' (image) posted to group {group} with caption.")
        else:
            await client.send_message(group, caption or f"📢 Flyer: {flyer_name}")
            log_debug(f"SUCCESS! Flyer '{flyer_name}' (text) posted to group {group}")
    except Exception as e:
        log_debug(f"[ERROR] Could not post flyer '{flyer_name}' to group {group}: {e}")
    # Cleanup the scheduled job after posting
    SCHEDULED_FLYER_JOBS.pop((flyer_name, group), None)

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

# === CANCEL COMMANDS BELOW ===

async def cancelflyer_handler(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can cancel flyers.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Usage: /cancelflyer <flyer_name> <group>")
        return
    flyer_name = args[1]
    group = resolve_group_name(args[2])
    job = SCHEDULED_FLYER_JOBS.get((flyer_name, group))
    if job:
        job.remove()
        del SCHEDULED_FLYER_JOBS[(flyer_name, group)]
        await message.reply(f"✅ Canceled scheduled flyer '{flyer_name}' for group {group}.")
        log_debug(f"Canceled scheduled flyer '{flyer_name}' for group {group}.")
    else:
        await message.reply("❌ No scheduled flyer found for that flyer/group.")
        log_debug(f"No scheduled flyer found to cancel for '{flyer_name}' in group {group}.")

async def cancelallflyers_handler(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can cancel all flyers.")
        return
    count = 0
    for job in list(SCHEDULED_FLYER_JOBS.values()):
        job.remove()
        count += 1
    SCHEDULED_FLYER_JOBS.clear()
    await message.reply(f"✅ Canceled all {count} scheduled flyers.")
    log_debug(f"Canceled all {count} scheduled flyers.")

# === LIST SCHEDULED FLYERS COMMAND ===

async def listscheduledflyers_handler(client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can check scheduled flyers.")
        return
    if not SCHEDULED_FLYER_JOBS:
        await message.reply("No flyers are currently scheduled.")
        return
    lines = ["Scheduled flyers:"]
    for (flyer_name, group), job in SCHEDULED_FLYER_JOBS.items():
        run_time = job.next_run_time
        lines.append(f"• <b>{flyer_name}</b> → <code>{group}</code> at <i>{run_time.strftime('%Y-%m-%d %H:%M:%S')}</i>")
    await message.reply('\n'.join(lines))

def register(app):
    log_debug("register() CALLED")
    app.add_handler(
        MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")),
        group=0
    )
    app.add_handler(
        MessageHandler(cancelflyer_handler, filters.command("cancelflyer")),
        group=0
    )
    app.add_handler(
        MessageHandler(cancelallflyers_handler, filters.command("cancelallflyers")),
        group=0
    )
    app.add_handler(
        MessageHandler(listscheduledflyers_handler, filters.command("listscheduledflyers")),
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
