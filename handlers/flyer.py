import os
import json
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.helpers import admin_only
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

FLYER_FILE = "data/flyers.json"
flyers = {}
scheduler = BackgroundScheduler()
scheduler.start()

if os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "r") as f:
        flyers = json.load(f)

def save_flyers():
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=4)

@Client.on_message(filters.command("addflyer") & filters.reply & filters.group)
@admin_only
async def add_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/addflyer FlyerName</code> (reply to image)")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    if not message.reply_to_message.photo:
        return await message.reply("You must reply to an image to set this flyer.")

    flyer_id = message.reply_to_message.photo.file_id
    flyers[flyer_name] = flyer_id
    save_flyers()

    await message.reply(f"✅ Flyer <b>{flyer_name}</b> added.")

@Client.on_message(filters.command("changeflyer") & filters.reply & filters.group)
@admin_only
async def change_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/changeflyer FlyerName</code> (reply to new image)")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    if not message.reply_to_message.photo:
        return await message.reply("You must reply to an image to change this flyer.")

    if flyer_name not in flyers:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")

    flyers[flyer_name] = message.reply_to_message.photo.file_id
    save_flyers()

    await message.reply(f"✅ Flyer <b>{flyer_name}</b> updated.")

@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/deleteflyer FlyerName</code>")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()

    if flyer_name not in flyers:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")

    del flyers[flyer_name]
    save_flyers()

    await message.reply(f"❌ Flyer <b>{flyer_name}</b> deleted.")

@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    if not flyers:
        return await message.reply("No flyers added yet.")

    flyer_list = "\n".join(f"• <code>{name}</code>" for name in flyers)
    await message.reply(f"📌 Available Flyers:\n\n{flyer_list}")

@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    if not message.text or len(message.text.split()) < 2:
        return await message.reply("Usage:\n<code>/flyer FlyerName</code>")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()

    if flyer_name not in flyers:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")

    await message.reply_photo(flyers[flyer_name])

@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer(client, message: Message):
    parts = message.text.split()
    if len(parts) != 4:
        return await message.reply("Usage:\n<code>/scheduleflyer FlyerName TargetGroupID HH:MM</code>")

    flyer_name, target_group, post_time = parts[1].lower(), parts[2], parts[3]
    try:
        hour, minute = map(int, post_time.split(":"))
        now = datetime.utcnow()
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)
    except:
        return await message.reply("Invalid time format. Use HH:MM (24-hour UTC)")

    if flyer_name not in flyers:
        return await message.reply("Flyer not found.")

    def send_flyer():
        try:
            client.send_photo(int(target_group), flyers[flyer_name])
        except Exception as e:
            print(f"Failed to post scheduled flyer: {e}")

    scheduler.add_job(send_flyer, trigger='date', run_date=scheduled_time)
    await message.reply(f"📆 Scheduled <b>{flyer_name}</b> for posting in <code>{target_group}</code> at <b>{post_time}</b> UTC")
