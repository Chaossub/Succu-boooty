import os
import re
import json
import logging
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.mongo import flyer_collection
from utils.check_admin import is_admin

# Group shortcut environment variables
GROUP_SHORTCUTS = {
    "SUCCUBUS_SANCTUARY": int(os.environ.get("SUCCUBUS_SANCTUARY", 0)),
    "MODELS_CHAT": int(os.environ.get("MODELS_CHAT", 0)),
    "TEST_GROUP": int(os.environ.get("TEST_GROUP", 0)),
}

# Schedule flyer posting
async def post_scheduled_flyer(client, name: str, group_id: int):
    flyer = flyer_collection.find_one({"name": name, "chat_id": group_id})
    if flyer:
        try:
            await client.send_photo(
                chat_id=group_id,
                photo=flyer["file_id"],
                caption=flyer.get("caption", "")
            )
        except Exception as e:
            logging.error(f"Failed to send scheduled flyer '{name}': {e}")

# Register flyer handlers
def register(app, scheduler: BackgroundScheduler):

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can schedule flyers.")

        parts = message.text.split(maxsplit=4)
        if len(parts) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <MM/DD HH:MM> <group shortcut>")

        flyer_name, date_str, group_key = parts[1], parts[2], parts[3].upper()
        group_id = GROUP_SHORTCUTS.get(group_key)

        if not group_id:
            return await message.reply("Invalid group shortcut.")

        try:
            post_time = datetime.strptime(date_str, "%m/%d %H:%M")
            post_time = post_time.replace(year=datetime.now().year)
        except ValueError:
            return await message.reply("Invalid time format. Use MM/DD HH:MM")

        scheduler.add_job(
            post_scheduled_flyer,
            "date",
            run_date=post_time,
            args=[client, flyer_name, group_id],
            id=f"flyer_{flyer_name}_{group_id}_{post_time.timestamp()}"
        )

        await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {post_time.strftime('%b %d, %I:%M %p')} in {group_key}")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No scheduled jobs found.")

        text = "<b>📅 Scheduled Flyers:</b>\n"
        for job in jobs:
            trigger_time = job.next_run_time.strftime("%m/%d %H:%M") if job.next_run_time else "N/A"
            text += f"• {job.id} — {trigger_time}\n"

        await message.reply(text)

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply("Usage: /canceljob <job_id>")

        job_id = parts[1]
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("No job found with that ID.")

        scheduler.remove_job(job_id)
        await message.reply(f"❌ Cancelled job: {job_id}")
