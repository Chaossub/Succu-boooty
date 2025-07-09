import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from pytz import timezone
from pymongo import MongoClient

# Logging
logger = logging.getLogger(__name__)

# Environment variables
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")

# Database
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers_collection = db["flyers"]
scheduled_collection = db["scheduled_flyers"]

# Timezone
LA = timezone("America/Los_Angeles")


def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not message.photo:
            await message.reply("Please attach a photo with your flyer.")
            return

        parts = message.text.split(None, 2)
        if len(parts) < 3:
            await message.reply("Usage: /addflyer <name> <caption>")
            return

        name, caption = parts[1], parts[2]
        flyers_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {
                "$set": {
                    "file_id": message.photo.file_id,
                    "caption": caption,
                    "chat_id": message.chat.id,
                }
            },
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{name}' saved!")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = message.command[1]
        flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            await message.reply("❌ Flyer not found.")
            return

        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message: Message):
        if not message.reply_to_message.photo:
            await message.reply("Please reply to a new photo.")
            return

        if len(message.command) < 2:
            await message.reply("Usage: /changeflyer <name>")
            return

        name = message.command[1]
        result = flyers_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.reply_to_message.photo.file_id}},
        )
        if result.matched_count == 0:
            await message.reply("❌ Flyer not found.")
        else:
            await message.reply(f"✅ Flyer '{name}' updated!")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if len(message.command) < 2:
            await message.reply("Usage: /deleteflyer <name>")
            return

        name = message.command[1]
        result = flyers_collection.delete_one(
            {"chat_id": message.chat.id, "name": name}
        )
        if result.deleted_count == 0:
            await message.reply("❌ Flyer not found.")
        else:
            await message.reply(f"🗑️ Flyer '{name}' deleted.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyers_collection.find({"chat_id": message.chat.id})
        names = [f"• {f['name']}" for f in flyers]
        if not names:
            await message.reply("No flyers found.")
        else:
            text = "📌 Flyers:\n" + "\n".join(names)
            await message.reply(text)

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        try:
            _, flyer_name, target_group_id, hour, minute = message.text.split()
            hour, minute = int(hour), int(minute)
        except ValueError:
            await message.reply(
                "Usage: /scheduleflyer <flyer_name> <target_group_id> <hour> <minute>"
            )
            return

        flyer = flyers_collection.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            await message.reply("❌ Flyer not found.")
            return

        now = datetime.now(LA)
        post_time = LA.localize(datetime(now.year, now.month, now.day, hour, minute))

        job_id = f"{message.chat.id}_{flyer_name}_{target_group_id}_{hour}_{minute}"
        scheduler.add_job(
            post_scheduled_flyer,
            trigger=DateTrigger(run_date=post_time),
            args=[app, flyer["file_id"], flyer["caption"], int(target_group_id)],
            id=job_id,
            replace_existing=True,
        )

        scheduled_collection.insert_one({
            "origin_chat": message.chat.id,
            "target_chat": int(target_group_id),
            "name": flyer_name,
            "run_time": post_time,
            "job_id": job_id,
        })

        await message.reply(f"⏰ Scheduled flyer '{flyer_name}' to post at {hour:02d}:{minute:02d} in {target_group_id}")

async def post_scheduled_flyer(app, file_id, caption, chat_id):
    try:
        await app.send_photo(chat_id, photo=file_id, caption=caption)
    except Exception as e:
        logging.error(f"Failed to send scheduled flyer: {e}")
