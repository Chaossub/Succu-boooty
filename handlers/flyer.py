import os
import json
import pytz
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.helpers import admin_only

FLYER_FILE = "data/flyers.json"
SCHEDULE_FILE = "data/flyer_schedule.json"
flyers = {}
schedule_data = {}
scheduler = BackgroundScheduler(timezone=pytz.timezone("America/Los_Angeles"))
scheduler.start()

if os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "r") as f:
        flyers = json.load(f)

if os.path.exists(SCHEDULE_FILE):
    with open(SCHEDULE_FILE, "r") as f:
        schedule_data = json.load(f)

def save_flyers():
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=4)

def save_schedule():
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule_data, f, indent=4)

@Client.on_message(filters.command("addflyer") & filters.reply & filters.group)
@admin_only
async def add_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/addflyer FlyerName</code> (reply to image)")
    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    if not message.reply_to_message.photo:
        return await message.reply("You must reply to an image to set this flyer.")
    flyer_id = message.reply_to_message.photo.file_id
    chat_id = str(message.chat.id)
    flyers.setdefault(chat_id, {})[flyer_name] = flyer_id
    save_flyers()
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> added.")

@Client.on_message(filters.command("changeflyer") & filters.reply & filters.group)
@admin_only
async def change_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/changeflyer FlyerName</code> (reply to new image)")
    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)
    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")
    if not message.reply_to_message.photo:
        return await message.reply("You must reply to an image to change this flyer.")
    flyers[chat_id][flyer_name] = message.reply_to_message.photo.file_id
    save_flyers()
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> updated.")

@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/deleteflyer FlyerName</code>")
    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)
    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")
    del flyers[chat_id][flyer_name]
    save_flyers()
    await message.reply(f"❌ Flyer <b>{flyer_name}</b> deleted.")

@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    chat_id = str(message.chat.id)
    if chat_id not in flyers or not flyers[chat_id]:
        return await message.reply("No flyers added yet.")
    flyer_list = "\n".join(f"• <code>{name}</code>" for name in flyers[chat_id])
    await message.reply(f"📌 Flyers in this group:\n\n{flyer_list}")

@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/flyer FlyerName</code>")
    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)
    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")
    await message.reply_photo(flyers[chat_id][flyer_name])

@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer(client, message: Message):
    try:
        _, flyer_name, post_time, target_group = message.text.split(maxsplit=3)
    except ValueError:
        return await message.reply("Usage:\n<code>/scheduleflyer flyername HH:MM target_group_id</code> (24h Los Angeles time)")

    flyer_name = flyer_name.lower()
    source_chat_id = str(message.chat.id)
    if source_chat_id not in flyers or flyer_name not in flyers[source_chat_id]:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found in this group.")

    if source_chat_id not in schedule_data:
        schedule_data[source_chat_id] = []

    flyer_id = flyers[source_chat_id][flyer_name]
    hour, minute = map(int, post_time.split(":"))
    target_chat_id = int(target_group)

    def post_flyer():
        try:
            client.send_photo(chat_id=target_chat_id, photo=flyer_id)
        except Exception as e:
            print(f"Failed to send flyer: {e}")

    job_id = f"{source_chat_id}_{flyer_name}_{post_time}"
    scheduler.add_job(post_flyer, "cron", hour=hour, minute=minute, id=job_id, replace_existing=True)
    schedule_data[source_chat_id].append({
        "flyer_name": flyer_name,
        "time": post_time,
        "target_chat_id": target_chat_id
    })
    save_schedule()
    await message.reply(f"🕓 Flyer <b>{flyer_name}</b> will be posted daily at <b>{post_time}</b> to group <code>{target_chat_id}</code>.")
