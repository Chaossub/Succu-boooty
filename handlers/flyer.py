import os
import json
import logging
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message, InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from bson.objectid import ObjectId

from utils.mongo import flyer_collection
from utils.check_admin import is_admin

logger = logging.getLogger(__name__)

# Optional: Shortcuts for group IDs
GROUP_SHORTCUTS = {
    "Succubus_Sanctuary": -1001234567890,
    "Models_Chat": -1002345678901,
    "Test_Group": -1003456789012
}

def register(app, scheduler):

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            await message.reply("❌ Usage: /flyer <name>")
            return
        name = message.command[1].lower()
        chat_id = message.chat.id
        flyer = flyer_collection.find_one({"chat_id": chat_id, "name": name})
        if not flyer:
            await message.reply("❌ Flyer not found.")
            return
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")

        if len(message.command) < 3 or not message.photo:
            return await message.reply("❌ Usage: Send an image with /addflyer <name> <caption>.")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:])
        chat_id = message.chat.id
        file_id = message.photo.file_id

        flyer_collection.update_one(
            {"chat_id": chat_id, "name": name},
            {"$set": {"caption": caption, "file_id": file_id}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' saved!")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can update flyers.")

        if len(message.command) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> [new caption] (reply with image optional)")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:]) if len(message.command) > 2 else None
        chat_id = message.chat.id

        flyer = flyer_collection.find_one({"chat_id": chat_id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        updates = {}
        if message.reply_to_message and message.reply_to_message.photo:
            updates["file_id"] = message.reply_to_message.photo.file_id
        if caption:
            updates["caption"] = caption

        if not updates:
            return await message.reply("❌ Provide new image or caption to update.")

        flyer_collection.update_one(
            {"chat_id": chat_id, "name": name},
            {"$set": updates}
        )
        await message.reply(f"✅ Flyer '{name}' updated!")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")

        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")

        name = message.command[1].lower()
        chat_id = message.chat.id
        result = flyer_collection.delete_one({"chat_id": chat_id, "name": name})

        if result.deleted_count:
            await message.reply(f"🗑 Flyer '{name}' deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        chat_id = message.chat.id
        flyers = flyer_collection.find({"chat_id": chat_id})
        names = [f"• {f['name']}" for f in flyers]
        if names:
            await message.reply("📂 Flyers in this group:\n" + "\n".join(names))
        else:
            await message.reply("📂 No flyers found.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")

        parts = message.text.split(" ", 4)
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <group_id or shortcut>")

        name, date_str, time_str, group_arg = parts[1], parts[2], parts[3], parts[4] if len(parts) > 4 else message.chat.id

        if group_arg in GROUP_SHORTCUTS:
            target_chat_id = GROUP_SHORTCUTS[group_arg]
        else:
            try:
                target_chat_id = int(group_arg)
            except ValueError:
                return await message.reply("❌ Invalid group ID or shortcut.")

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name.lower()})
        if not flyer:
            return await message.reply("❌ Flyer not found in this group.")

        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("❌ Invalid datetime format. Use YYYY-MM-DD HH:MM")

        job_id = f"flyer_{str(ObjectId())}"

        scheduler.add_job(
            lambda: client.send_photo(
                chat_id=target_chat_id,
                photo=flyer["file_id"],
                caption=flyer["caption"]
            ),
            trigger=DateTrigger(run_date=dt),
            id=job_id
        )
        await message.reply(f"📅 Scheduled flyer '{name}' to post at {dt} in group {target_chat_id}.\nUse /cancelpost {job_id} to cancel.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("📭 No scheduled posts.")

        lines = [
            f"• {job.id}: {job.next_run_time.strftime('%Y-%m-%d %H:%M')}"
            for job in jobs
        ]
        await message.reply("📋 Scheduled Posts:\n" + "\n".join(lines))

    @app.on_message(filters.command("cancelpost") & filters.group)
    async def cancel_post(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can cancel scheduled posts.")

        if len(message.command) < 2:
            return await message.reply("❌ Usage: /cancelpost <job_id>")

        job_id = message.command[1]
        job = scheduler.get_job(job_id)
        if job:
            job.remove()
            await message.reply(f"❌ Canceled scheduled post {job_id}.")
        else:
            await message.reply("❌ Job not found.")
