# handlers/schedulemsg.py
import os
import asyncio
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.handlers import MessageHandler

# ────────────── CONFIG ──────────────

OWNER_ID = 6964994611  # Roni 💕

scheduler = BackgroundScheduler()
MAIN_LOOP = None  # set by main.py
SCHEDULED_MSGS = {}  # msg_id -> job


def log_debug(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[SCHEDULEMSG][{ts}] {msg}", flush=True)


def resolve_group_name(group: str) -> str:
    """
    Accept either:
      • '-1001234567890'
      • '@channelusername'
      • ENV shortcut like SUCCUBUS_SANCTUARY / MODELS_CHAT
    """
    if group.startswith("-") or group.startswith("@"):
        return group

    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()

    return group


def set_main_loop(loop) -> None:
    """Called from main.py so jobs can post back into the bot loop."""
    global MAIN_LOOP
    MAIN_LOOP = loop
    log_debug("MAIN_LOOP set by set_main_loop()")


# ────────────── CORE HANDLERS ──────────────

async def schedulemsg_handler(client, message):
    log_debug(
        f"schedulemsg_handler CALLED in chat {message.chat.id} "
        f"by {message.from_user.id if message.from_user else '???'} "
        f"text={message.text!r}"
    )

    # Owner only
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can schedule messages.")
        return

    # We allow:
    # /schedulemsg YYYY-MM-DD HH:MM GROUP TEXT...
    # /sm         YYYY-MM-DD HH:MM GROUP TEXT...
    text_cmd = message.text or ""
    args = text_cmd.split(maxsplit=4)

    # Photo logic (message or reply)
    photo = None
    if message.photo:
        photo = message.photo.file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo.file_id

    if len(args) < 5 and not photo:
        await message.reply(
            "Usage:\n"
            "/schedulemsg <YYYY-MM-DD HH:MM> <group> <text>\n"
            "or /sm <YYYY-MM-DD HH:MM> <group> <text>\n\n"
            "Attach a photo or reply to one to schedule an image."
        )
        return

    date_part, time_part = args[1], args[2]
    group = resolve_group_name(args[3])
    text = args[4] if len(args) > 4 else ""
    time_str = f"{date_part} {time_part}"

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(
            datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        )
    except Exception as e:  # noqa: BLE001
        await message.reply(f"❌ Invalid time: {e}")
        return

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
            f"ID: <code>{msg_id}</code>"
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
            f"ID: <code>{msg_id}</code>"
        )
        log_debug(f"Message scheduled: {msg_id}")


async def post_msg(client, group: str, text: str, msg_id: str):
    log_debug(f"post_msg CALLED for {group}: {text} (msg_id={msg_id})")
    try:
        await client.send_message(group, text)
        log_debug(f"Message posted to {group} (msg_id={msg_id})")
    except Exception as e:  # noqa: BLE001
        log_debug(f"Failed to post scheduled message: {e}")
    SCHEDULED_MSGS.pop(msg_id, None)


def run_post_msg(client, group: str, text: str, msg_id: str):
    log_debug(f"run_post_msg CALLED for {group}: {text} (msg_id={msg_id})")
    global MAIN_LOOP

    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set!")
        return

    try:
        fut = asyncio.run_coroutine_threadsafe(
            post_msg(client, group, text, msg_id),
            MAIN_LOOP,
        )
        log_debug(f"asyncio.run_coroutine_threadsafe called for post_msg (future={fut})")
    except Exception as exc:  # noqa: BLE001
        log_debug(f"ERROR in run_post_msg: {exc}")


async def post_photo(client, group: str, photo: str, caption: str, msg_id: str):
    log_debug(f"post_photo CALLED for {group}: {caption} (msg_id={msg_id})")
    try:
        await client.send_photo(group, photo, caption=caption)
        log_debug(f"Photo posted to {group} (msg_id={msg_id})")
    except Exception as e:  # noqa: BLE001
        log_debug(f"Failed to post scheduled photo: {e}")
    SCHEDULED_MSGS.pop(msg_id, None)


def run_post_photo(client, group: str, photo: str, caption: str, msg_id: str):
    log_debug(f"run_post_photo CALLED for {group}: {caption} (msg_id={msg_id})")
    global MAIN_LOOP

    if MAIN_LOOP is None:
        log_debug("ERROR: MAIN_LOOP is not set!")
        return

    try:
        fut = asyncio.run_coroutine_threadsafe(
            post_photo(client, group, photo, caption, msg_id),
            MAIN_LOOP,
        )
        log_debug(f"asyncio.run_coroutine_threadsafe called for post_photo (future={fut})")
    except Exception as exc:  # noqa: BLE001
        log_debug(f"ERROR in run_post_photo: {exc}")


async def cancelmsg_handler(client, message):
    if not message.from_user or message.from_user.id != OWNER_ID:
        await message.reply("Only the owner can cancel scheduled messages.")
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /cancelmsg <msg_id>")
        return

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
        await message.reply("Only the owner can list scheduled messages.")
        return

    if not SCHEDULED_MSGS:
        await message.reply("No scheduled messages.")
        return

    lines = ["Scheduled messages:"]
    for msg_id, job in SCHEDULED_MSGS.items():
        group = msg_id.split("|", 1)[0]
        rt = getattr(job, "next_run_time", None)
        run_time = rt.strftime("%Y-%m-%d %H:%M:%S") if rt else "unknown"
        lines.append(f"• <b>{group}</b> at <i>{run_time}</i> — <code>{msg_id}</code>")

    await message.reply("\n".join(lines))


# ────────────── REGISTRATION ──────────────

def register(app):
    log_debug("Registering schedulemsg handlers")

    # Normal command handler: /schedulemsg or /sm
    app.add_handler(
        MessageHandler(
            schedulemsg_handler,
            filters.command(["schedulemsg", "sm"]),
        ),
        group=0,
    )

    # Fallback: if for some reason filters.command doesn't catch it,
    # also match raw text starting with /schedulemsg or /sm
    app.add_handler(
        MessageHandler(
            schedulemsg_handler,
            filters.regex(r"^/(schedulemsg|sm)\b"),
        ),
        group=1,
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
