from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS
from utils.check_admin import is_admin

def register(app, scheduler: BackgroundScheduler):
    async def send_flyer_now(client, chat_id: int, name: str):
        flyer = await flyer_collection.find_one({"name": name, "chat_id": chat_id})
        if not flyer:
            return
        if flyer.get("file_id"):
            await client.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])
        else:
            await client.send_message(chat_id, flyer["caption"])

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = message.command[1].lower()
        flyer = await flyer_collection.find_one({"name": name, "chat_id": message.chat.id})
        if not flyer:
            return await message.reply("Flyer not found.")
        if flyer.get("file_id"):
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply(flyer["caption"])

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can add flyers.")
        if len(message.command) < 3:
            return await message.reply("Usage: /addflyer <name> <caption>")
        name = message.command[1].lower()
        caption = " ".join(message.command[2:])
        file_id = message.photo.file_id if message.photo else None
        await flyer_collection.update_one(
            {"name": name, "chat_id": message.chat.id},
            {"$set": {"caption": caption, "file_id": file_id}},
            upsert=True
        )
        await message.reply("✅ Flyer saved.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        names = [f["name"] async for f in flyers]
        if not names:
            return await message.reply("No flyers saved yet.")
        await message.reply("📂 Saved Flyers:
" + "
".join(f"• {n}" for n in names))

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can update flyers.")
        if not message.reply_to_message or not message.command:
            return await message.reply("Reply to a new image and use: /changeflyer <name>")
        name = message.command[1].lower()
        caption = " ".join(message.command[2:]) or message.reply_to_message.caption or ""
        file_id = message.reply_to_message.photo.file_id if message.reply_to_message.photo else None
        await flyer_collection.update_one(
            {"name": name, "chat_id": message.chat.id},
            {"$set": {"caption": caption, "file_id": file_id}},
            upsert=True
        )
        await message.reply("✅ Flyer updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = message.command[1].lower()
        await flyer_collection.delete_one({"name": name, "chat_id": message.chat.id})
        await message.reply("🗑️ Flyer deleted.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can schedule flyers.")
        if len(message.command) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <group>")
        name = message.command[1].lower()
        time_str = message.command[2]
        group_key = message.command[3]
        group_id = GROUP_SHORTCUTS.get(group_key, None)
        if not group_id:
            return await message.reply("Invalid group shortcut.")
        try:
            run_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("Invalid datetime format. Use YYYY-MM-DD HH:MM")
        job_id = f"{group_id}_{name}"
        scheduler.add_job(send_flyer_now, "date", run_date=run_time, args=[client, group_id, name], id=job_id)
        await scheduled_jobs.insert_one({"_id": job_id, "name": name, "group_id": group_id, "time": run_time})
        await message.reply(f"📅 Scheduled flyer '{name}' for {time_str} in {group_key}.")

    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancel_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Only admins can cancel scheduled flyers.")
        if len(message.command) < 3:
            return await message.reply("Usage: /cancelflyer <name> <group>")
        name = message.command[1].lower()
        group_key = message.command[2]
        group_id = GROUP_SHORTCUTS.get(group_key, None)
        if not group_id:
            return await message.reply("Invalid group shortcut.")
        job_id = f"{group_id}_{name}"
        scheduler.remove_job(job_id)
        await scheduled_jobs.delete_one({"_id": job_id})
        await message.reply(f"❌ Canceled scheduled flyer '{name}' in {group_key}.")
