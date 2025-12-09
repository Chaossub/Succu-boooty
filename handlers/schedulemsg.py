# handlers/schedulemsg.py
import os
import asyncio
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.handlers import MessageHandler


# Owner (falls back to your usual default)
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))

# APScheduler instance (runs in its own thread)
scheduler = BackgroundScheduler()

# Event loop from main.py – must be injected via set_main_loop()
MAIN_LOOP = None

# Simple in-memory store of scheduled jobs: msg_id -> APScheduler Job
SCHEDULED_MSGS = {}  # type: dict[str, object]


def log_debug(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[SCHEDULEMSG][{ts}] {msg}", flush=True)


def resolve_group_name(group: str) -> str:
    """
    Allow passing either:
      • raw chat id (starts with '-')
      • @username
      • ENV shortcut like MODELS_CHAT, TEST_GROUP, etc.
    """
    if group.startswith("-") or group.startswith("@"):
        return group

    val = os.environ.get(group)
    if val:
        # If you ever store comma-separated ids, take the first
        return val.split(",")[0].strip()

    return group


def set_main_loop(loop) -> None:
    """
    Called from main.py so the scheduler thread can safely
    schedule coroutines on the bot's event loop.
    """
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set by set_main_loop()")


async def schedulemsg_handler(client, message):
    log_debug("schedulemsg_handler CALLED")

    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can schedule messages.")

    # We expect:
    # /schedulemsg YYYY-MM-DD HH:MM GROUP_NAME optional text...
    text_cmd = message.text or message.caption or ""
    args = text_cmd.split(maxsplit=4)

    if len(args) < 4 and not (
        message.photo
        or (message.reply_to_message and message.reply_to_message.photo)
    ):
        return await message.reply(
            """Usage: /schedulemsg <YYYY-MM-DD> <HH:MM> <GROUP_OR_ENV> <text>

Attach a photo or reply to one to schedule a photo.
Example:
  /schedulemsg 2025-07-20 18:30 MODELS_CHAT Hello!
(or attach/reply to a photo and run the command)"""
        )

    if len(args) < 4:
        return await message.reply(
            "Missing pieces. Format is:\n"
            "/schedulemsg 2025-07-20 18:30 MODELS_CHAT Optional text"
        )

    date_part = args[1]
    time_part = args[2]
    group = resolve_group_name(args[3])
    text = args[4] if len(args) > 4 else ""

    time_str = f"{date_part} {time_part}"

    # Photo logic
    photo = None
    if message.photo:
        photo = message.photo.file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo.file_id

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:  # noqa: BLE001
        return await message.reply(f"❌ Invalid time: {e}")

    msg_id = f"{group}|{int(post_time.timestamp())}"

    if photo:
        job = scheduler.add_job(
            func=run_post_photo,
            trigger="date",
            run_date=post_time,
            args=[client, group, photo, text, msg_id],
        )
        SCHEDULED_MSGS[msg_id] = job
        await message.reply(
            f"✅ Photo scheduled for {post_time.strftime('%Y-%m-%d %H:%M %Z')} in {group}.\n"
            f"ID: `{msg_id}`"
        )
        log_debug(f"Photo scheduled: {msg_id}")
    else:
        job = scheduler.add_job(
            func=run_post_msg,
            trigger="date",
            run_date=post_time,
            args=[client, group, text, msg_id],
        )
        SCHEDULED_MSGS[msg_id] = job
        await message.reply(
            f"✅ Message scheduled for {post_time.strftime('%Y-%m-%d %H:%M %Z')} in {group}.\n"
            f"ID: `{msg_id}`"
        )
        log_debug(f"Message scheduled: {msg_id}")


async def post_msg(client, group: str, text: str, msg_id: str):
    log_debug(f"post_msg CALLED for {group}: {text} (msg_id={msg_id})")
    try:
        await client.send_message(group, text)
        log_debug(f"Message posted to {group} (msg_id={msg_id})")
    except Exception as e:  # noqa: BLE001
        log_debug(f"Failed to post scheduled message: {e}")
    finally:
        SCHEDULED_MSGS.pop(msg_id, None)


def run_post_msg(client, group: str, text: str, msg_id: str):
    log_debug(f"run_post_msg CALLED for {group}: {text} (msg_id={msg_id})")
    global MAIN_LOOP

    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set!")
        return

    try:
        asyncio.run_coroutine_threadsafe(
            post_msg(client, group, text, msg_id),
            MAIN_LOOP,
        )
        log_debug("asyncio.run_coroutine_threadsafe called for post_msg")
    except Exception as exc:  # noqa: BLE001
        log_debug(f"ERROR in run_post_msg: {exc}")


async def post_photo(client, group: str, photo: str, caption: str, msg_id: str):
    log_debug(f"post_photo CALLED for {group}: {caption} (msg_id={msg_id})")
    try:
        await client.send_photo(group, photo, caption=caption)
        log_debug(f"Photo posted to {group} (msg_id={msg_id})")
    except Exception as e:  # noqa: BLE001
        log_debug(f"Failed to post scheduled photo: {e}")
    finally:
        SCHEDULED_MSGS.pop(msg_id, None)


def run_post_photo(client, group: str, photo: str, caption: str, msg_id: str):
    log_debug(f"run_post_photo CALLED for {group}: {caption} (msg_id={msg_id})")
    global MAIN_LOOP

    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set!")
        return

    try:
        asyncio.run_coroutine_threadsafe(
            post_photo(client, group, photo, caption, msg_id),
            MAIN_LOOP,
        )
        log_debug("asyncio.run_coroutine_threadsafe called for post_photo")
    except Exception as exc:  # noqa: BLE001
        log_debug(f"ERROR in run_post_photo: {exc}")


async def cancelmsg_handler(client, message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can cancel scheduled messages.")

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("Usage: /cancelmsg <msg_id>")

    msg_id = args[1].strip()
    job = SCHEDULED_MSGS.get(msg_id)

    if job:
        try:
            job.remove()
        except Exception:
            pass
        SCHEDULED_MSGS.pop(msg_id, None)
        await message.reply(f"✅ Scheduled message {msg_id} canceled.")
        log_debug(f"Canceled scheduled message: {msg_id}")
    else:
        await message.reply("❌ No such scheduled message.")


async def listmsgs_handler(client, message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can list scheduled messages.")

    if not SCHEDULED_MSGS:
        return await message.reply("No scheduled messages.")

    lines = ["Scheduled messages:"]
    for msg_id, job in SCHEDULED_MSGS.items():
        group = msg_id.split("|", 1)[0]
        run_time = getattr(job, "next_run_time", None)
        if run_time is not None:
            run_time_str = run_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            run_time_str = "unknown time"
        lines.append(f"• {group} at {run_time_str} — `{msg_id}`")

    await message.reply("\n".join(lines))


def register(app):
    log_debug("Registering schedulemsg handlers")

    app.add_handler(
        MessageHandler(schedulemsg_handler, filters.command("schedulemsg")),
        group=0,
    )
    app.add_handler(
        MessageHandler(cancelmsg_handler, filters.command("cancelmsg")),
        group=0,
    )
    app.add_handler(
        MessageHandler(listmsgs_handler, filters.command("listmsgs")),
        group=0,
    )

    if not scheduler.running:
        scheduler.start()
        log_debug("Scheduler started")
