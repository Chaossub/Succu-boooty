import os
import random
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.check_admin import is_admin
from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS

def register(app, scheduler: BackgroundScheduler):
    async def send_flyer_to_group(name, chat_id):
        flyer = await flyer_collection.find_one({"name": name})
        if not flyer:
            return
        await app.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = message.command[1].lower()
        flyer = await flyer_collection.find_one({"name": name})
        if not flyer:
            return await message.reply("Flyer not found.")
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find()
        flyer_names = [f'• {doc["name"]}' async for doc in flyers]
        if not flyer_names:
            return await message.reply("No flyers found.")
        await message.reply("<b>📂 Available Flyers:</b>\n" + "\n".join(flyer_names))

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(message):
            return await message.reply("Only admins can create flyers.")

        if not message.photo:
            return await message.reply("Please attach an image with your flyer.")

        parts = message.caption.split(" ", 2) if message.caption else []
        if len(parts) < 3:
            return await message.reply("Usage: /addflyer <name> <caption> (as photo caption)")

        _, name, caption = parts
        name = name.lower()

        flyer_data = {
            "name": name,
            "caption": caption,
            "file_id": message.photo.file_id
        }

        await flyer_collection.update_one({"name": name}, {"$set": flyer_data}, upsert=True)
        await message.reply(f"✅ Flyer <b>{name}</b> added or updated.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(message):
            return await message.reply("Only admins can change flyers.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("Reply to a new image with: /changeflyer <name> [new caption]")

        parts = message.text.split(" ", 2)
        if len(parts) < 2:
            return await message.reply("Usage: /changeflyer <name> [new caption]")

        name = parts[1].lower()
        caption = parts[2] if len(parts) > 2 else None

        flyer = await flyer_collection.find_one({"name": name})
        if not flyer:
            return await message.reply("Flyer not found.")

        update = {"file_id": message.reply_to_message.photo.file_id}
        if caption:
            update["caption"] = caption

        await flyer_collection.update_one({"name": name}, {"$set": update})
        await message.reply(f"✅ Flyer <b>{name}</b> updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(message):
            return await message.reply("Only admins can delete flyers.")
        if len(message.command) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = message.command[1].lower()
        result = await flyer_collection.delete_one({"name": name})
        if result.deleted_count:
            await message.reply(f"🗑 Flyer <b>{name}</b> deleted.")
        else:
            await message.reply("Flyer not found.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(message):
            return await message.reply("Only admins can schedule flyers.")
        parts = message.text.split(" ", 3)
        if len(parts) < 4:
            return await message.reply("Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <group shortcut or ID>")

        name, time_str, group_arg = parts[1], parts[2], parts[3]
        target_group = GROUP_SHORTCUTS.get(group_arg.upper(), group_arg)

        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("Invalid time format. Use YYYY-MM-DD HH:MM")

        job_id = f"{name}_{dt.timestamp()}_{target_group}"
        scheduler.add_job(
            send_flyer_to_group,
            "date",
            run_date=dt,
            args=[name.lower(), int(target_group)],
            id=job_id
        )

        await scheduled_jobs.insert_one({"job_id": job_id, "flyer": name, "time": dt, "chat_id": int(target_group)})
        await message.reply(f"✅ Flyer <b>{name}</b> scheduled for <b>{dt}</b> to group <code>{group_arg}</code>.")

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        if not await is_admin(message):
            return await message.reply("Only admins can cancel jobs.")
        if len(message.command) < 2:
            return await message.reply("Usage: /canceljob <job_id>")

        job_id = message.command[1]
        job = scheduler.get_job(job_id)
        if job:
            job.remove()
            await scheduled_jobs.delete_one({"job_id": job_id})
            await message.reply(f"❌ Job <b>{job_id}</b> cancelled.")
        else:
            await message.reply("No such job found.")
