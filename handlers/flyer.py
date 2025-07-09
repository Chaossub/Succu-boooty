import os
import json
import logging
from datetime import datetime
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.helpers import admin_only

# ─── Constants ──────────────────────────────────────────────────────────────
FLYER_FILE = "data/flyers.json"
SCHEDULE_FILE = "data/scheduled_flyers.json"
TZ = timezone("America/Los_Angeles")
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.start()

# ─── Load Data ──────────────────────────────────────────────────────────────
flyers = {}
scheduled = {}

if os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "r") as f:
        flyers = json.load(f)

if os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "r") as f:
        scheduled = json.load(f)

# ─── Save Functions ─────────────────────────────────────────────────────────
def save_flyers():
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=2)

def save_scheduled():
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(scheduled, f, indent=2)

# ─── Flyer Commands ─────────────────────────────────────────────────────────
@Client.on_message(filters.command("addflyer") & filters.reply & filters.group)
@admin_only()
async def add_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage: /addflyer FlyerName (reply to image)")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    if not message.reply_to_message.photo:
        return await message.reply("❌ You must reply to an image.")

    flyer_id = message.reply_to_message.photo.file_id
    chat_id = str(message.chat.id)

    flyers.setdefault(chat_id, {})[flyer_name] = flyer_id
    save_flyers()
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> added.")


@Client.on_message(filters.command("changeflyer") & filters.reply & filters.group)
@admin_only()
async def change_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage: /changeflyer FlyerName (reply to new image)")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"❌ No flyer named <b>{flyer_name}</b> found.")

    if not message.reply_to_message.photo:
        return await message.reply("❌ You must reply to an image.")

    flyers[chat_id][flyer_name] = message.reply_to_message.photo.file_id
    save_flyers()
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> updated.")


@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only()
async def delete_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage: /deleteflyer FlyerName")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"❌ No flyer named <b>{flyer_name}</b> found.")

    del flyers[chat_id][flyer_name]
    save_flyers()
    await message.reply(f"❌ Flyer <b>{flyer_name}</b> deleted.")


@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    chat_id = str(message.chat.id)
    if chat_id not in flyers or not flyers[chat_id]:
        return await message.reply("No flyers added yet.")

    msg = "\n".join(f"• <code>{name}</code>" for name in flyers[chat_id])
    await message.reply(f"📌 Flyers in this group:\n\n{msg}")


@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage: /flyer FlyerName")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"❌ No flyer named <b>{flyer_name}</b> found.")

    await message.reply_photo(flyers[chat_id][flyer_name])


# ─── Scheduling ─────────────────────────────────────────────────────────────
@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only()
async def schedule_flyer(client, message: Message):
    parts = message.text.split()
    if len(parts) < 4:
        return await message.reply("Usage: /scheduleflyer FlyerName HH:MM TargetGroupID")

    flyer_name, time_str, target_chat_id = parts[1].lower(), parts[2], parts[3]
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"❌ Flyer <b>{flyer_name}</b> not found.")

    try:
        post_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return await message.reply("❌ Invalid time format. Use HH:MM (24h).")

    flyer_id = flyers[chat_id][flyer_name]
    job_id = f"{chat_id}_{flyer_name}_{target_chat_id}"

    def send_flyer():
        try:
            client.send_photo(int(target_chat_id), flyer_id)
            logging.info(f"✅ Sent flyer {flyer_name} to {target_chat_id}")
        except Exception as e:
            logging.error(f"❌ Failed to send flyer: {e}")

    # Schedule daily posting
    scheduler.add_job(
        send_flyer,
        trigger="cron",
        hour=post_time.hour,
        minute=post_time.minute,
        id=job_id,
        replace_existing=True,
    )

    scheduled.setdefault(chat_id, {})[flyer_name] = {
        "time": time_str,
        "target": target_chat_id
    }
    save_scheduled()

    await message.reply(f"📅 Scheduled flyer <b>{flyer_name}</b> daily at {time_str} to group <code>{target_chat_id}</code>.")
