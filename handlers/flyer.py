import os
import logging
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS
from utils.check_admin import is_admin

logger = logging.getLogger(__name__)

def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only admins can create flyers.")

        if not message.photo:
            return await message.reply("📸 Please attach an image with the flyer.")

        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply("Usage: /addflyer <name> <caption> (with photo)")
        name, caption = parts[1], parts[2]

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {
                "chat_id": message.chat.id,
                "name": name,
                "caption": caption,
                "file_id": message.photo.file_id
            }},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = parts[1]
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("⚠️ Flyer not found.")
        await client.send_photo(
            chat_id=message.chat.id,
            photo=flyer["file_id"],
            caption=flyer["caption"]
        )

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        names = [f"• {flyer['name']}" for flyer in flyers]
        if not names:
            return await message.reply("No flyers found.")
        await message.reply("📂 Saved Flyers:\n" + "\n".join(names))

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only admins can update flyers.")
        if not message.reply_to_message.photo:
            return await message.reply("Reply to a photo to update flyer image.")

        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Usage: /changeflyer <name> (reply to new photo)")
        name = parts[1]

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.reply_to_message.photo.file_id}}
        )
        await message.reply(f"✅ Flyer '{name}' image updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only admins can delete flyers.")

        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = parts[1]

        result = flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})
        if result.deleted_count == 0:
            return await message.reply("⚠️ Flyer not found.")
        await message.reply(f"🗑️ Flyer '{name}' deleted.")

    def parse_schedule_args(text):
        parts = text.split(maxsplit=4)
        if len(parts) < 4:
            return None, None, None, None
        name = parts[1]
        date_str = parts[2]
        group_ref = parts[3]
        extra = parts[4] if len(parts) > 4 else ""
        return name, date_str, group_ref, extra

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only admins can schedule flyers.")
        name, date_str, group_ref, _ = parse_schedule_args(message.text)
        if not all([name, date_str, group_ref]):
            return await message.reply("Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD HH:MM> <group>")

        group_id = GROUP_SHORTCUTS.get(group_ref.upper(), group_ref)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("⚠️ Invalid date format. Use YYYY-MM-DD HH:MM")

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("⚠️ Flyer not found.")

        job_id = f"flyer_{message.chat.id}_{name}_{dt.timestamp()}"
        scheduler.add_job(
            lambda: client.send_photo(group_id, flyer["file_id"], caption=flyer["caption"]),
            trigger="date", run_date=dt, id=job_id
        )
        scheduled_jobs.insert_one({
            "job_id": job_id,
            "type": "flyer",
            "group_id": group_id,
            "chat_id": message.chat.id,
            "flyer_name": name,
            "datetime": dt
        })
        await message.reply(f"📅 Scheduled flyer '{name}' for {date_str} in {group_ref}.")

    @app.on_message(filters.command("scheduletext") & filters.group)
    async def schedule_text(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("🚫 Only admins can schedule text posts.")
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            return await message.reply("Usage: /scheduletext <name> <YYYY-MM-DD HH:MM> <group> <message>")
        name, date_str, group_ref, text = parts[1], parts[2], parts[3], parts[4]

        group_id = GROUP_SHORTCUTS.get(group_ref.upper(), group_ref)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("⚠️ Invalid date format. Use YYYY-MM-DD HH:MM")

        job_id = f"text_{message.chat.id}_{name}_{dt.timestamp()}"
        scheduler.add_job(
            lambda: client.send_message(group_id, text),
            trigger="date", run_date=dt, id=job_id
        )
        scheduled_jobs.insert_one({
            "job_id": job_id,
            "type": "text",
            "group_id": group_id,
            "chat_id": message.chat.id,
            "text": text,
            "datetime": dt
        })
        await message.reply(f"📅 Scheduled text post '{name}' for {date_str} in {group_ref}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = list(scheduled_jobs.find({"chat_id": message.chat.id}))
        if not jobs:
            return await message.reply("🗓 No scheduled jobs found.")
        lines = []
        for job in jobs:
            time_str = job["datetime"].strftime("%Y-%m-%d %H:%M")
            target = job.get("group_id", "")
            name = job.get("flyer_name", job.get("text", "text"))
            lines.append(f"• {job['type'].capitalize()} '{name}' → {target} at {time_str}")
        await message.reply("📅 Scheduled Jobs:\n" + "\n".join(lines))

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Usage: /canceljob <job_id>")
        job_id = parts[1]
        scheduler.remove_job(job_id)
        scheduled_jobs.delete_one({"job_id": job_id})
        await message.reply("❌ Job cancelled.")
