import os
import re
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message
from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def resolve_group_id(shortcut_or_id: str) -> int:
    if shortcut_or_id in GROUP_SHORTCUTS:
        return GROUP_SHORTCUTS[shortcut_or_id]
    try:
        return int(shortcut_or_id)
    except ValueError:
        return 0

def register(app):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can add flyers.")
        
        if not message.photo:
            return await message.reply("Please attach a photo for the flyer.")
        
        if len(message.command) < 3:
            return await message.reply("Usage: /addflyer <name> <caption> (with attached photo)")
        
        name = message.command[1].lower()
        caption = " ".join(message.command[2:])
        file_id = message.photo.file_id

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def send_flyer(client, message: Message):
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
        flyer_list = [f"• {f['name']}" for f in flyers]
        if not flyer_list:
            return await message.reply("No flyers found.")
        await message.reply("<b>📂 Flyers:</b>\n" + "\n".join(flyer_list))

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can update flyers.")

        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a new image to update the flyer.")
        
        if len(message.command) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")

        name = message.command[1].lower()
        new_caption = " ".join(message.command[2:]) or flyer_collection.find_one(
            {"chat_id": message.chat.id, "name": name}
        ).get("caption", "")

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": message.reply_to_message.photo.file_id, "caption": new_caption}},
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{name}' updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can delete flyers.")
        
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")

        name = message.command[1].lower()
        result = flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})

        if result.deleted_count:
            await message.reply(f"🗑 Flyer '{name}' deleted.")
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can schedule flyers.")
        
        if len(message.command) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <group shortcut or ID>")
        
        name = message.command[1].lower()
        time_str = message.command[2]
        group_key = message.command[3]

        try:
            post_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("⚠ Invalid time format. Use YYYY-MM-DD HH:MM")

        group_id = resolve_group_id(group_key)
        if not group_id:
            return await message.reply("⚠ Invalid group shortcut or ID.")

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        job_id = f"{message.chat.id}_{name}_{int(post_time.timestamp())}"

        def send_scheduled():
            app.send_photo(group_id, flyer["file_id"], caption=flyer["caption"])

        scheduler.add_job(send_scheduled, trigger="date", run_date=post_time, id=job_id)
        scheduled_jobs.insert_one({
            "job_id": job_id,
            "name": name,
            "chat_id": message.chat.id,
            "group_id": group_id,
            "post_time": post_time.isoformat(),
        })
        await message.reply(f"📅 Flyer '{name}' scheduled for {post_time} to group {group_key}.")

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancel_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can cancel flyer jobs.")

        if len(message.command) < 2:
            return await message.reply("Usage: /cancelflyer <job_id>")

        job_id = message.command[1]
        scheduler.remove_job(job_id)
        scheduled_jobs.delete_one({"job_id": job_id})
        await message.reply(f"❌ Canceled scheduled flyer job: {job_id}")
