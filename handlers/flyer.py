import os
import json
import logging
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import Message
from utils.mongo import flyer_collection
from utils.check_admin import is_admin

GROUP_SHORTCUTS = {
    "Succubus_Sanctuary": int(os.environ.get("SUCCUBUS_SANCTUARY", 0)),
    "Models_Chat": int(os.environ.get("MODELS_CHAT", 0)),
    "Test_Group": int(os.environ.get("TEST_GROUP", 0))
}

def parse_datetime(dt_str: str) -> datetime | None:
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return None

def register(app, scheduler):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can add flyers.")
        if not message.photo or len(message.command) < 3:
            return await message.reply("Usage: /addflyer <name> <caption> (with photo)")
        name, caption = message.command[1], " ".join(message.command[2:])
        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"caption": caption, "file_id": message.photo.file_id}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = message.command[1]
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        names = [f"• {f['name']}" for f in flyers]
        await message.reply("📂 Flyers:\n" + "\n".join(names) if names else "No flyers saved.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = message.command[1]
        flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})
        await message.reply(f"🗑 Flyer '{name}' deleted.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can change flyers.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to the new flyer image.")
        if len(message.command) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")
        name = message.command[1]
        new_caption = " ".join(message.command[2:]) if len(message.command) > 2 else None
        update = {"file_id": message.reply_to_message.photo.file_id}
        if new_caption:
            update["caption"] = new_caption
        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": update}
        )
        await message.reply(f"✅ Flyer '{name}' updated.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(message.from_user, message.chat):
            return await message.reply("Only admins can schedule flyers.")
        if len(message.command) < 3:
            return await message.reply("Usage: /scheduleflyer <name> <datetime or shortcut>")
        name, time_arg = message.command[1], message.command[2]
        target_chat = message.command[3] if len(message.command) > 3 else message.chat.id
        target_id = GROUP_SHORTCUTS.get(target_chat, int(target_chat)) if isinstance(target_chat, str) else target_chat
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        dt = parse_datetime(time_arg)
        if not dt:
            return await message.reply("❌ Invalid time format. Use MM/DD/YYYY HH:MM or MM/DD HH:MM.")

        job_id = f"flyer_{name}_{message.chat.id}_{dt.timestamp()}"

        async def post_flyer():
            await app.send_photo(target_id, flyer["file_id"], caption=flyer["caption"])

        scheduler.add_job(post_flyer, trigger="date", run_date=dt, id=job_id)
        await message.reply(f"📅 Flyer '{name}' scheduled for {dt} in {target_chat}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduler.get_jobs()
        lines = []
        for job in jobs:
            lines.append(f"• {job.id} — {job.next_run_time.strftime('%m/%d %H:%M')}")
        await message.reply("🗓 Scheduled Posts:\n" + "\n".join(lines) if lines else "No scheduled flyers.")

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /canceljob <job_id>")
        job_id = message.command[1]
        job = scheduler.get_job(job_id)
        if not job:
            return await message.reply("❌ Job not found.")
        scheduler.remove_job(job_id)
        await message.reply(f"❌ Job '{job_id}' cancelled.")
