# handlers/flyer_scheduler.py
import logging
import asyncio
import os
import sys
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# ────────────── SCHEDULER & LOOP ──────────────
scheduler = BackgroundScheduler(timezone=pytz.timezone("America/Los_Angeles"))
MAIN_LOOP = None  # Will be set by main.py

# ────────────── MONGO ──────────────
mongo_uri = os.getenv("MONGO_URI")
mongo_db = os.getenv("MONGO_DBNAME")
flyer_client = MongoClient(mongo_uri)[mongo_db]
flyer_collection = flyer_client["flyers"]

MAX_CAPTION_LENGTH = 1024

# Use same owner logic as main.py
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))

# Track jobs for cancellation: key = (flyer_name, group)
SCHEDULED_FLYER_JOBS: dict[tuple[str, str], object] = {}


def log_debug(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[SCHEDULER][{ts}] {msg}"
    # Log to file
    try:
        with open("/tmp/scheduler_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Failed to write to log file: {e}", file=sys.stderr)
    # Log to stdout
    print(line, flush=True)


def resolve_group_name(group: str) -> str:
    """Resolve env shortcuts like MODELS_CHAT into real chat IDs/usernames."""
    if group.startswith("-") or group.startswith("@"):
        return group
    val = os.environ.get(group)
    if val:
        # allow comma list like "id1,id2"
        return val.split(",")[0].strip()
    return group


log_debug("flyer_scheduler.py module loaded!")


# ────────────── COMMAND HANDLERS ──────────────
async def scheduleflyer_handler(client, message: Message):
    log_debug(f"scheduleflyer_handler CALLED by user {message.from_user.id if message.from_user else 'unknown'}")
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can schedule flyers.")
        return

    # /scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <GROUP_ENV_OR_ID>
    args = (message.text or "").split(maxsplit=4)
    log_debug(f"scheduleflyer_handler ARGS: {args}")
    if len(args) < 5:
        await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <group>\n\n"
            "Example:\n"
            "/scheduleflyer tipping 2025-07-17 19:54 MODELS_CHAT"
        )
        log_debug("scheduleflyer_handler: Not enough arguments!")
        return

    flyer_name = args[1].strip().lower()
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

    # Avoid scheduling in the past
    now = datetime.now(tz=pytz.timezone("America/Los_Angeles"))
    if post_time <= now:
        await message.reply("❌ That time is in the past. Pick a future time.")
        log_debug(f"[ERROR] Tried to schedule in the past: {post_time} <= {now}")
        return

    # Pre-check chat
    try:
        await client.get_chat(group)
        log_debug(f"client.get_chat({group}) succeeded before scheduling.")
    except Exception as e:
        log_debug(f"[ERROR] client.get_chat({group}) failed: {e}")
        await message.reply(f"❌ I can't access that group: {e}")
        return

    log_debug(f"Scheduling flyer '{flyer_name}' to group {group} at {post_time}")

    try:
        job = scheduler.add_job(
            func=run_post_flyer,
            trigger="date",
            run_date=post_time,
            args=[client, flyer_name, group],
        )
        SCHEDULED_FLYER_JOBS[(flyer_name, group)] = job
        log_debug(f"Job scheduled for flyer '{flyer_name}' in group {group} at {post_time}")
        await message.reply(
            f"✅ Scheduled flyer '<b>{flyer_name}</b>' for <code>{time_str}</code> in <code>{group}</code>.",
            disable_web_page_preview=True,
        )
    except Exception as e:
        log_debug(f"[ERROR] Could not schedule job: {e}")
        await message.reply(f"❌ Failed to schedule flyer: {e}")


async def post_flyer(client, flyer_name: str, group: str):
    log_debug(f"post_flyer CALLED with flyer_name={flyer_name}, group={group}")
    try:
        flyer = flyer_collection.find_one({"name": flyer_name})
    except Exception as e:
        log_debug(f"[ERROR] Mongo lookup failed for flyer '{flyer_name}': {e}")
        await client.send_message(group, f"❌ Failed to load flyer '{flyer_name}' from DB.")
        return

    log_debug(f"Loaded flyer from DB: {flyer}")
    if not flyer:
        log_debug(f"[ERROR] Flyer '{flyer_name}' not found in DB.")
        await client.send_message(group, f"❌ Flyer '{flyer_name}' not found.")
        return

    try:
        caption = flyer.get("caption", "") or ""
        file_id = flyer.get("file_id")

        if file_id and isinstance(file_id, str) and file_id.strip():
            send_caption = caption[:MAX_CAPTION_LENGTH]
            await client.send_photo(group, file_id, caption=send_caption)
            log_debug(f"SUCCESS! Flyer '{flyer_name}' (image) posted to group {group} with caption.")
        else:
            text = caption or f"📢 Flyer: {flyer_name}"
            await client.send_message(group, text)
            log_debug(f"SUCCESS! Flyer '{flyer_name}' (text) posted to group {group}")
    except Exception as e:
        log_debug(f"[ERROR] Could not post flyer '{flyer_name}' to group {group}: {e}")
    finally:
        # Cleanup the scheduled job after posting (if present)
        if (flyer_name, group) in SCHEDULED_FLYER_JOBS:
            SCHEDULED_FLYER_JOBS.pop((flyer_name, group), None)
            log_debug(f"Job entry removed from SCHEDULED_FLYER_JOBS for ({flyer_name}, {group})")


def run_post_flyer(client, flyer_name: str, group: str):
    log_debug(f"run_post_flyer CALLED for flyer_name={flyer_name}, group={group}")
    global MAIN_LOOP

    if MAIN_LOOP is None:
        try:
            MAIN_LOOP = asyncio.get_event_loop()
            log_debug("MAIN_LOOP was None, get_event_loop() succeeded")
        except Exception as e:
            log_debug(f"[ERROR] MAIN_LOOP get_event_loop failed: {e}")
            return

    try:
        asyncio.run_coroutine_threadsafe(post_flyer(client, flyer_name, group), MAIN_LOOP)
        log_debug(f"Submitted post_flyer task to MAIN_LOOP for flyer '{flyer_name}' in group {group}")
    except Exception as e:
        log_debug(f"[ERROR] Failed to submit post_flyer to MAIN_LOOP: {e}")


# ────────────── CANCEL / LIST COMMANDS ──────────────
async def cancelflyer_handler(client, message: Message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can cancel flyers.")
        return

    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Usage: /cancelflyer <flyer_name> <group>")
        return

    flyer_name = args[1].strip().lower()
    group = resolve_group_name(args[2])

    job = SCHEDULED_FLYER_JOBS.get((flyer_name, group))
    if job:
        try:
            job.remove()
        except Exception as e:
            log_debug(f"[ERROR] cancelflyer job.remove() failed: {e}")
        SCHEDULED_FLYER_JOBS.pop((flyer_name, group), None)
        await message.reply(f"✅ Canceled scheduled flyer '<b>{flyer_name}</b>' for group <code>{group}</code>.")
        log_debug(f"Canceled scheduled flyer '{flyer_name}' for group {group}.")
    else:
        await message.reply("❌ No scheduled flyer found for that flyer/group.")
        log_debug(f"No scheduled flyer found to cancel for '{flyer_name}' in group {group}.")


async def cancelallflyers_handler(client, message: Message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can cancel all flyers.")
        return

    count = 0
    for key, job in list(SCHEDULED_FLYER_JOBS.items()):
        try:
            job.remove()
            count += 1
        except Exception as e:
            log_debug(f"[ERROR] cancelallflyers_handler job.remove() failed for {key}: {e}")

    SCHEDULED_FLYER_JOBS.clear()
    await message.reply(f"✅ Canceled all {count} scheduled flyers.")
    log_debug(f"Canceled all {count} scheduled flyers.")


async def listscheduledflyers_handler(client, message: Message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can check scheduled flyers.")
        return

    if not SCHEDULED_FLYER_JOBS:
        await message.reply("No flyers are currently scheduled.")
        return

    lines = ["<b>Scheduled flyers:</b>"]
    for (flyer_name, group), job in SCHEDULED_FLYER_JOBS.items():
        run_time = job.next_run_time
        when = run_time.strftime("%Y-%m-%d %H:%M:%S") if run_time else "unknown"
        lines.append(f"• <b>{flyer_name}</b> → <code>{group}</code> at <i>{when}</i>")

    await message.reply("\n".join(lines), disable_web_page_preview=True)


def register(app):
    log_debug("register() CALLED in flyer_scheduler")

    app.add_handler(
        MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(cancelflyer_handler, filters.command("cancelflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(cancelallflyers_handler, filters.command("cancelallflyers")),
        group=0,
    )
    app.add_handler(
        MessageHandler(listscheduledflyers_handler, filters.command("listscheduledflyers")),
        group=0,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started in flyer_scheduler.")
        log_debug("Scheduler started in flyer_scheduler.")


def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set from main.py")
