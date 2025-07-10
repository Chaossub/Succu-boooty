import os
import json
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

# MongoDB Setup
from pymongo import MongoClient
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
if not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DBNAME environment variable.")
mongo_client = MongoClient(MONGO_URI)
flyers_db = mongo_client[MONGO_DB]["flyers"]

SUPER_ADMIN_ID = 6964994611  # Your Telegram ID

# Admin check
async def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def register(app, scheduler: BackgroundScheduler):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only group admins can use this command.")

        if not message.photo or len(message.command) < 3:
            return await message.reply("Usage: /addflyer <name> <ad> (with photo attached)")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:])
        flyer = {
            "chat_id": message.chat.id,
            "name": name,
            "caption": caption,
            "file_id": message.photo.file_id
        }

        flyers_db.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": flyer},
            upsert=True
        )

        await message.reply(f"✅ Flyer <b>{name}</b> has been added.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")

        name = message.command[1].lower()
        flyer = flyers_db.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ No flyer found with that name.")

        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyers_db.find({"chat_id": message.chat.id})
        names = [f"• {f['name']}" for f in flyers]
        if not names:
            return await message.reply("No flyers have been added yet.")
        await message.reply("<b>📂 Saved Flyers:</b>\n" + "\n".join(names))

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only group admins can use this command.")

        if len(message.command) < 2:
            return await message.reply("Usage: /changeflyer <name> (with new image attached or caption)")

        name = message.command[1].lower()
        flyer = flyers_db.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ No flyer found with that name.")

        update = {}
        if message.photo:
            update["file_id"] = message.photo.file_id
        if len(message.command) > 2:
            update["caption"] = " ".join(message.command[2:])

        if not update:
            return await message.reply("Send a new image or new caption.")

        flyers_db.update_one({"chat_id": message.chat.id, "name": name}, {"$set": update})
        await message.reply(f"✅ Flyer <b>{name}</b> has been updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only group admins can use this command.")

        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")

        name = message.command[1].lower()
        result = flyers_db.delete_one({"chat_id": message.chat.id, "name": name})
        if result.deleted_count == 0:
            return await message.reply("❌ No flyer found with that name.")
        await message.reply(f"🗑 Flyer <b>{name}</b> has been deleted.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only group admins can schedule flyers.")

        if len(message.command) < 3:
            return await message.reply("Usage: /scheduleflyer <name> <HH:MM or YYYY-MM-DD HH:MM>")

        name = message.command[1].lower()
        time_str = " ".join(message.command[2:])
        flyer = flyers_db.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ No flyer found with that name.")

        try:
            dt = datetime.strptime(time_str, "%H:%M")
            now = datetime.now()
            run_time = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
            if run_time < now:
                run_time = run_time.replace(day=now.day + 1)
        except ValueError:
            try:
                run_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                return await message.reply("❌ Invalid time format.")

        async def post_flyer():
            await app.send_photo(
                message.chat.id,
                flyer["file_id"],
                caption=flyer["caption"]
            )

        scheduler.add_job(post_flyer, "date", run_date=run_time)
        await message.reply(f"📅 Scheduled <b>{name}</b> to post at {run_time.strftime('%Y-%m-%d %H:%M')}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only group admins can view scheduled jobs.")

        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No flyer jobs are currently scheduled.")
        response = "<b>🗓 Scheduled Flyer Posts:</b>\n"
        for job in jobs:
            response += f"• ID: {job.id} | Run At: {job.next_run_time}\n"
        await message.reply(response)
