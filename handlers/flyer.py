import os
import re
import logging
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS
from utils.check_admin import is_admin

log = logging.getLogger(__name__)

def register(app, scheduler):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can add flyers.")

        if not message.photo:
            return await message.reply("Please attach an image with the command.")

        if len(message.command) < 3:
            return await message.reply("Usage: /addflyer <name> <caption>")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:])
        file_id = message.photo.file_id

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' added!")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = message.command[1].lower()
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        names = [f"• <code>{f['name']}</code>" for f in flyers]
        if not names:
            return await message.reply("No flyers found.")
        await message.reply("<b>📂 Flyers:</b>\n" + "\n".join(names))

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = message.command[1].lower()
        flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})
        await message.reply(f"❌ Flyer '{name}' deleted.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can update flyers.")

        if len(message.command) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")

        name = message.command[1].lower()
        caption = " ".join(message.command[2:]) if len(message.command) > 2 else None
        update = {}

        if message.reply_to_message and message.reply_to_message.photo:
            update["file_id"] = message.reply_to_message.photo.file_id

        if caption:
            update["caption"] = caption

        if not update:
            return await message.reply("Reply to a new image or provide a new caption.")

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": update}
        )
        await message.reply(f"✏️ Flyer '{name}' updated!")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can schedule flyers.")

        if len(message.command) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <datetime> <group_id or shortcut>")

        name = message.command[1].lower()
        datetime_str = message.command[2]
        target_group = message.command[3]

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        # Convert group shortcut to ID
        group_id = GROUP_SHORTCUTS.get(target_group.upper(), target_group)

        try:
            group_id = int(group_id)
        except ValueError:
            return await message.reply("Invalid group ID or shortcut.")

        try:
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("Invalid time format. Use YYYY-MM-DD HH:MM")

        job = scheduler.add_job(
            send_flyer,
            "date",
            run_date=dt,
            args=[client, group_id, flyer["file_id"], flyer["caption"]],
            id=f"{name}_{group_id}_{dt.isoformat()}",
            misfire_grace_time=300
        )

        scheduled_jobs.insert_one({
            "job_id": job.id,
            "flyer_name": name,
            "group_id": group_id,
            "time": dt.isoformat()
        })

        await message.reply(f"📅 Flyer '{name}' scheduled for {dt} in group {group_id}")

    @app.on_message(filters.command("cancelschedule") & filters.group)
    async def cancel_schedule(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can cancel schedules.")

        if len(message.command) < 2:
            return await message.reply("Usage: /cancelschedule <job_id>")

        job_id = message.command[1]
        job = scheduler.get_job(job_id)

        if not job:
            return await message.reply("No such scheduled job found.")

        job.remove()
        scheduled_jobs.delete_one({"job_id": job_id})
        await message.reply(f"🗑 Canceled schedule '{job_id}'.")

    async def send_flyer(client, group_id, file_id, caption):
        try:
            await client.send_photo(group_id, file_id, caption=caption)
        except Exception as e:
            log.error(f"Failed to send scheduled flyer: {e}")
