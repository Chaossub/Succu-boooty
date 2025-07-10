import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime
from utils.mongo import flyer_collection, scheduled_jobs
from utils.check_admin import is_admin
from utils.groups import GROUP_SHORTCUTS

scheduler = BackgroundScheduler()
scheduler.start()
logging.getLogger("apscheduler").setLevel(logging.WARNING)

def schedule_flyer_post(app, flyer, chat_id, run_time, job_id):
    async def job():
        try:
            if flyer["file_id"].startswith("AgAC"):  # Photo
                await app.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])
            else:
                await app.send_document(chat_id, flyer["file_id"], caption=flyer["caption"])
        except Exception as e:
            logging.error(f"Failed to send scheduled flyer: {e}")
    scheduler.add_job(job, trigger="date", run_date=run_time, id=job_id)
    scheduled_jobs.insert_one({"job_id": job_id, "flyer": flyer["name"], "chat_id": chat_id, "run_time": run_time})

def register(app):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can add flyers.")
        if not message.photo and not message.document:
            return await message.reply("You must attach a photo or document with the flyer.")

        try:
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                return await message.reply("Usage: /addflyer <name> <caption>")
            name, caption = args[1], args[2]
            file = message.photo[-1] if message.photo else message.document
            flyer_collection.update_one(
                {"chat_id": message.chat.id, "name": name},
                {"$set": {
                    "chat_id": message.chat.id,
                    "name": name,
                    "file_id": file.file_id,
                    "caption": caption
                }},
                upsert=True
            )
            await message.reply(f"✅ Flyer '{name}' saved!")
        except Exception as e:
            await message.reply(f"Error: {e}")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = message.command[1]
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")
        if flyer["file_id"].startswith("AgAC"):  # Photo
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply_document(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can change flyers.")
        if not message.reply_to_message.photo and not message.reply_to_message.document:
            return await message.reply("Reply to a photo or document to update.")
        if len(message.command) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")
        name = message.command[1]
        new_caption = " ".join(message.command[2:]) if len(message.command) > 2 else None
        file = message.reply_to_message.photo[-1] if message.reply_to_message.photo else message.reply_to_message.document
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")
        flyer["file_id"] = file.file_id
        if new_caption:
            flyer["caption"] = new_caption
        flyer_collection.update_one({"_id": flyer["_id"]}, {"$set": flyer})
        await message.reply(f"✅ Flyer '{name}' updated!")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = message.command[1]
        result = flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})
        if result.deleted_count:
            await message.reply(f"🗑 Flyer '{name}' deleted.")
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = list(flyer_collection.find({"chat_id": message.chat.id}))
        if not flyers:
            return await message.reply("No flyers found.")
        names = [f"• {f['name']}" for f in flyers]
        await message.reply("<b>📂 Flyers:</b>\n" + "\n".join(names))

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can schedule flyers.")
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <group>")
        name, datetime_str, group_key = parts[1], parts[2], parts[3]
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        try:
            run_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("Invalid datetime format. Use YYYY-MM-DD HH:MM")

        target_chat_id = GROUP_SHORTCUTS.get(group_key, group_key)
        job_id = f"{message.chat.id}_{name}_{run_time.timestamp()}"
        schedule_flyer_post(client, flyer, target_chat_id, run_time, job_id)
        await message.reply(f"⏰ Scheduled flyer '{name}' to post in {group_key} at {run_time}.\nUse /listjobs to see jobs.")

    @app.on_message(filters.command("cancelschedule") & filters.group)
    async def cancel_schedule(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can cancel jobs.")
        if len(message.command) < 2:
            return await message.reply("Usage: /cancelschedule <job_id>")
        job_id = message.command[1]
        try:
            scheduler.remove_job(job_id)
            scheduled_jobs.delete_one({"job_id": job_id})
            await message.reply(f"❌ Canceled scheduled job: {job_id}")
        except JobLookupError:
            await message.reply("Job ID not found.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = list(scheduled_jobs.find())
        if not jobs:
            return await message.reply("No scheduled flyers.")
        text = "<b>📅 Scheduled Flyers:</b>\n"
        for job in jobs:
            text += f"• {job['flyer']} ➜ {job['chat_id']} at {job['run_time']} (`{job['job_id']}`)\n"
        await message.reply(text)
