import os
import json
import pytz
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.decorators import admin_only

FLYER_FILE = "data/flyers.json"
flyers = {}

if os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "r") as f:
        flyers = json.load(f)

def save_flyers():
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=4)

# ─── Add Flyer ─────────────────────────────────────────────
@Client.on_message(filters.command("addflyer") & filters.photo & filters.group)
@admin_only
async def add_flyer(client, message: Message):
    if not message.caption or len(message.caption.split()) < 2:
        return await message.reply("Usage:\nSend a photo with caption:\n<code>/addflyer FlyerName Caption text</code>")

    args = message.caption.split(maxsplit=1)
    flyer_name = args[0].lower()
    caption = args[1]
    file_id = message.photo.file_id
    chat_id = str(message.chat.id)

    if chat_id not in flyers:
        flyers[chat_id] = {}

    flyers[chat_id][flyer_name] = {
        "file_id": file_id,
        "caption": caption
    }
    save_flyers()

    await message.reply(f"✅ Flyer <b>{flyer_name}</b> added.")

# ─── Change Flyer ──────────────────────────────────────────
@Client.on_message(filters.command("changeflyer") & filters.photo & filters.group)
@admin_only
async def change_flyer(client, message: Message):
    if not message.caption or len(message.caption.split()) < 2:
        return await message.reply("Usage:\nSend a photo with caption:\n<code>/changeflyer FlyerName Caption</code>")

    args = message.caption.split(maxsplit=1)
    flyer_name = args[0].lower()
    caption = args[1]
    file_id = message.photo.file_id
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"Flyer <b>{flyer_name}</b> not found.")

    flyers[chat_id][flyer_name] = {
        "file_id": file_id,
        "caption": caption
    }
    save_flyers()

    await message.reply(f"✅ Flyer <b>{flyer_name}</b> updated.")

# ─── Delete Flyer ──────────────────────────────────────────
@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage:\n<code>/deleteflyer FlyerName</code>")

    flyer_name = message.command[1].lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"Flyer <b>{flyer_name}</b> not found.")

    del flyers[chat_id][flyer_name]
    save_flyers()

    await message.reply(f"❌ Flyer <b>{flyer_name}</b> deleted.")

# ─── List Flyers ───────────────────────────────────────────
@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    chat_id = str(message.chat.id)
    if chat_id not in flyers or not flyers[chat_id]:
        return await message.reply("No flyers added yet.")

    flyer_list = "\n".join(f"• <code>{name}</code>" for name in flyers[chat_id])
    await message.reply(f"📌 Flyers in this group:\n\n{flyer_list}")

# ─── Get Flyer ─────────────────────────────────────────────
@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage:\n<code>/flyer FlyerName</code>")

    flyer_name = message.command[1].lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"Flyer <b>{flyer_name}</b> not found.")

    flyer = flyers[chat_id][flyer_name]
    await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

# ─── Schedule Flyer ────────────────────────────────────────
@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer(client, message: Message):
    if len(message.command) < 5:
        return await message.reply("Usage:\n<code>/scheduleflyer FlyerName Hour Minute TargetGroupID</code>")

    flyer_name = message.command[1].lower()
    hour = int(message.command[2])
    minute = int(message.command[3])
    target_group = message.command[4]
    source_chat = str(message.chat.id)

    if source_chat not in flyers or flyer_name not in flyers[source_chat]:
        return await message.reply(f"Flyer <b>{flyer_name}</b> not found in this group.")

    flyer = flyers[source_chat][flyer_name]

    job_id = f"{source_chat}_{flyer_name}_{target_group}"

    def send_flyer():
        try:
            client.send_photo(
                chat_id=target_group,
                photo=flyer["file_id"],
                caption=flyer["caption"]
            )
        except Exception as e:
            print(f"[SCHED ERROR] Failed to send flyer: {e}")

    la_tz = pytz.timezone("America/Los_Angeles")
    scheduler.add_job(
        send_flyer,
        trigger="cron",
        hour=hour,
        minute=minute,
        timezone=la_tz,
        id=job_id,
        replace_existing=True
    )

    await message.reply(f"⏰ Flyer <b>{flyer_name}</b> scheduled to post in <code>{target_group}</code> at {hour:02d}:{minute:02d} LA time.")

