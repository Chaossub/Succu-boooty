import os
import asyncio
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.handlers import MessageHandler
import traceback

OWNER_ID = 6964994611
scheduler = BackgroundScheduler()
MAIN_LOOP = None  # Set by main.py
SCHEDULED_MSGS = {}  # msg_id -> job

def resolve_group_name(group):
    if group.startswith('-') or group.startswith('@'):
        return group
    val = os.environ.get(group)
    if val:
        return val.split(",")[0].strip()
    return group

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    print("[SCHEDULEMSG] MAIN_LOOP set.")

async def schedulemsg_handler(client, message):
    print("[SCHEDULEMSG] schedulemsg_handler called")
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can schedule messages.")
    args = message.text.split(maxsplit=4)
    if len(args) < 5 and not (message.photo or (message.reply_to_message and message.reply_to_message.photo)):
        return await message.reply(
            "Usage: /schedulemsg <YYYY-MM-DD HH:MM> <group> <text or caption>\n"
            "Attach a photo or reply to one to schedule a photo.\n"
            "Example:\n/schedulemsg 2025-07-20 18:30 MODELS_CHAT Hello!\n"
            "(or attach/reply to a photo and run the command)"
        )
    date_part, time_part, group = args[1], args[2], resolve_group_name(args[3])
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
    except Exception as e:
        print(f"[SCHEDULEMSG][ERROR] Time parse failed: {e}")
        return await message.reply(f"❌ Invalid time: {e}")

    msg_id = f"{group}|{int(post_time.timestamp())}"
    if photo:
        job = scheduler.add_job(
            func=run_post_photo,
            trigger='date',
            run_date=post_time,
            args=[client, group, photo, text, msg_id]
        )
        SCHEDULED_MSGS[msg_id] = job
        print(f"[SCHEDULEMSG] Scheduled photo job for {group} at {post_time} (msg_id={msg_id})")
        await message.reply(f"✅ Photo scheduled for {post_time.strftime('%Y-%m-%d %H:%M %Z')} in {group}.\nID: <code>{msg_id}</code>")
    else:
        job = scheduler.add_job(
            func=run_post_msg,
            trigger='date',
            run_date=post_time,
            args=[client, group, text, msg_id]
        )
        SCHEDULED_MSGS[msg_id] = job
        print(f"[SCHEDULEMSG] Scheduled text job for {group} at {post_time} (msg_id={msg_id})")
        await message.reply(f"✅ Message scheduled for {post_time.strftime('%Y-%m-%d %H:%M %Z')} in {group}.\nID: <code>{msg_id}</code>")

async def post_msg(client, group, text, msg_id):
    print(f"[SCHEDULEMSG][post_msg] Trying to post message to {group}: {text!r}")
    try:
        await client.send_message(group, text)
        print(f"[SCHEDULEMSG][post_msg] Successfully posted message to {group}.")
    except Exception as e:
        print(f"[SCHEDULEMSG][post_msg][ERROR] Failed to post scheduled message: {e}\n{traceback.format_exc()}")
    SCHEDULED_MSGS.pop(msg_id, None)

def run_post_msg(client, group, text, msg_id):
    global MAIN_LOOP
    if MAIN_LOOP is None:
        print("[SCHEDULEMSG][ERROR] MAIN_LOOP is not set!")
        return
    try:
        fut = asyncio.run_coroutine_threadsafe(post_msg(client, group, text, msg_id), MAIN_LOOP)
        try:
            exc = fut.exception(timeout=5)
            if exc:
                print(f"[SCHEDULEMSG][ERROR] Exception in post_msg coroutine: {exc}\n{traceback.format_exc()}")
            else:
                print(f"[SCHEDULEMSG] post_msg scheduled successfully for {group} (msg_id={msg_id})")
        except Exception as e:
            print(f"[SCHEDULEMSG][ERROR] Could not get future exception: {e}\n{traceback.format_exc()}")
    except Exception as e:
        print(f"[SCHEDULEMSG][ERROR] Could not schedule post_msg: {e}\n{traceback.format_exc()}")

async def post_photo(client, group, photo, caption, msg_id):
    print(f"[SCHEDULEMSG][post_photo] Trying to post photo to {group}.")
    try:
        await client.send_photo(group, photo, caption=caption)
        print(f"[SCHEDULEMSG][post_photo] Successfully posted photo to {group}.")
    except Exception as e:
        print(f"[SCHEDULEMSG][post_photo][ERROR] Failed to post scheduled photo: {e}\n{traceback.format_exc()}")
    SCHEDULED_MSGS.pop(msg_id, None)

def run_post_photo(client, group, photo, caption, msg_id):
    global MAIN_LOOP
    if MAIN_LOOP is None:
        print("[SCHEDULEMSG][ERROR] MAIN_LOOP is not set!")
        return
    try:
        fut = asyncio.run_coroutine_threadsafe(post_photo(client, group, photo, caption, msg_id), MAIN_LOOP)
        try:
            exc = fut.exception(timeout=5)
            if exc:
                print(f"[SCHEDULEMSG][ERROR] Exception in post_photo coroutine: {exc}\n{traceback.format_exc()}")
            else:
                print(f"[SCHEDULEMSG] post_photo scheduled successfully for {group} (msg_id={msg_id})")
        except Exception as e:
            print(f"[SCHEDULEMSG][ERROR] Could not get future exception: {e}\n{traceback.format_exc()}")
    except Exception as e:
        print(f"[SCHEDULEMSG][ERROR] Could not schedule post_photo: {e}\n{traceback.format_exc()}")

async def cancelmsg_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can cancel scheduled messages.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("Usage: /cancelmsg <msg_id>")
    msg_id = args[1].strip()
    job = SCHEDULED_MSGS.get(msg_id)
    if job:
        job.remove()
        del SCHEDULED_MSGS[msg_id]
        print(f"[SCHEDULEMSG] Canceled scheduled message {msg_id}")
        await message.reply(f"✅ Scheduled message {msg_id} canceled.")
    else:
        print(f"[SCHEDULEMSG] Tried to cancel unknown message {msg_id}")
        await message.reply("❌ No such scheduled message.")

async def listmsgs_handler(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("Only the owner can list scheduled messages.")
    if not SCHEDULED_MSGS:
        return await message.reply("No scheduled messages.")
    lines = ["Scheduled messages:"]
    for msg_id, job in SCHEDULED_MSGS.items():
        group = msg_id.split("|", 1)[0]
        run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"• <b>{group}</b> at <i>{run_time}</i> — <code>{msg_id}</code>")
    await message.reply('\n'.join(lines))

def register(app):
    print("[SCHEDULEMSG] Registering schedulemsg handlers")
    app.add_handler(MessageHandler(schedulemsg_handler, filters.command("schedulemsg")), group=0)
    app.add_handler(MessageHandler(cancelmsg_handler, filters.command("cancelmsg")), group=0)
    app.add_handler(MessageHandler(listmsgs_handler, filters.command("listmsgs")), group=0)
    if not scheduler.running:
        scheduler.start()
        print("[SCHEDULEMSG] Scheduler started")

def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
    print("[SCHEDULEMSG] MAIN_LOOP set by set_main_loop()")
