import os
import json
import logging
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from bson.objectid import ObjectId

# Load environment variables
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB") or os.environ.get("MONGO_DBNAME")

if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DB environment variable.")

from pymongo import MongoClient
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
flyers_collection = db["flyers"]

SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id, user):
    if not user:
        return False
    if user.id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user.id)
        return member.status in ("administrator", "creator")
    except:
        return False

def register(app, scheduler: BackgroundScheduler):

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("Usage: /flyer <name>")

        name = args[1].strip().lower()
        flyer = flyers_collection.find_one({"name": name})
        if flyer:
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyers_collection.find()
        flyer_list = [f"• <b>{f['name']}</b>" for f in flyers]
        if flyer_list:
            await message.reply("📂 <b>Flyers:</b>\n" + "\n".join(flyer_list))
        else:
            await message.reply("No flyers found.")

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user):
            return await message.reply("Only admins can add flyers.")

        if not message.photo or not message.caption:
            return await message.reply("Attach a photo and include caption as: /addflyer <name> <caption>")

        try:
            parts = message.caption.split(None, 2)
            name = parts[1].strip().lower()
            caption = parts[2].strip()
        except:
            return await message.reply("Invalid format. Use: /addflyer <name> <caption>")

        flyers_collection.update_one(
            {"name": name},
            {"$set": {"file_id": message.photo.file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer <b>{name}</b> saved.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user):
            return await message.reply("Only admins can change flyers.")

        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to the new image with: /changeflyer <name> [new caption]")

        args = message.text.split(None, 2)
        if len(args) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")

        name = args[1].strip().lower()
        caption = args[2].strip() if len(args) > 2 else None
        update = {"file_id": message.reply_to_message.photo.file_id}
        if caption:
            update["caption"] = caption

        result = flyers_collection.update_one({"name": name}, {"$set": update})
        if result.matched_count:
            await message.reply(f"✅ Flyer <b>{name}</b> updated.")
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user):
            return await message.reply("Only admins can delete flyers.")

        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("Usage: /deleteflyer <name>")

        name = args[1].strip().lower()
        result = flyers_collection.delete_one({"name": name})
        if result.deleted_count:
            await message.reply(f"🗑 Flyer <b>{name}</b> deleted.")
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user):
            return await message.reply("Only admins can schedule flyers.")

        args = message.text.split(None, 3)
        if len(args) < 3:
            return await message.reply("Usage: /scheduleflyer <name> <datetime> [chat_id]")

        name = args[1].strip().lower()
        time_str = args[2].strip()
        target_chat = int(args[3]) if len(args) > 3 else message.chat.id

        flyer = flyers_collection.find_one({"name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        try:
            dt = datetime.strptime(time_str, "%m/%d/%Y %H:%M")
        except ValueError:
            return await message.reply("Invalid time format. Use MM/DD/YYYY HH:MM")

        job_id = f"{target_chat}_{name}"

        def send_flyer():
            try:
                app.send_photo(chat_id=target_chat, photo=flyer["file_id"], caption=flyer["caption"])
            except Exception as e:
                logging.error(f"Failed to send scheduled flyer {name}: {e}")

        scheduler.add_job(send_flyer, trigger=DateTrigger(run_date=dt), id=job_id, replace_existing=True)
        await message.reply(f"📅 Flyer <b>{name}</b> scheduled for <code>{time_str}</code> in chat <code>{target_chat}</code>.")

    @app.on_message(filters.command("cancelscheduled") & filters.group)
    async def cancel_scheduled_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user):
            return await message.reply("Only admins can cancel scheduled flyers.")

        parts = message.text.split()
        if len(parts) != 3:
            return await message.reply("Usage: /cancelscheduled <flyer_name> <chat_id>")

        flyer_name, chat_id = parts[1], parts[2]
        job_id = f"{chat_id}_{flyer_name.lower()}"

        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            await message.reply(f"✅ Scheduled post for flyer <b>{flyer_name}</b> in chat <code>{chat_id}</code> cancelled.")
        else:
            await message.reply("⚠ No such scheduled flyer found.")

