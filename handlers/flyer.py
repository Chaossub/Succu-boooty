import os
import re
from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

from utils.mongo import flyer_collection, scheduled_jobs
from utils.groups import GROUP_SHORTCUTS
from utils.check_admin import is_admin

def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can add flyers.")

        if not message.photo:
            return await message.reply("❌ Please attach a photo when using /addflyer.")

        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")

        name = args[1].lower()
        caption = args[2]
        file_id = message.photo.file_id

        flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )

        await message.reply(f"✅ Flyer '{name}' saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            return await message.reply("❌ Usage: /flyer <name>")

        name = args[1].lower()
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})

        if not flyer:
            return await message.reply("❌ Flyer not found.")

        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        flyer_names = [f"- {flyer['name']}" for flyer in flyers]

        if not flyer_names:
            return await message.reply("📂 No flyers saved yet.")

        await message.reply("📂 Saved Flyers:\n" + "\n".join(flyer_names))

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can delete flyers.")

        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")

        name = args[1].lower()
        result = flyer_collection.delete_one({"chat_id": message.chat.id, "name": name})

        if result.deleted_count:
            await message.reply(f"🗑 Flyer '{name}' deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can change flyers.")

        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Please reply to a photo to update the flyer image.")

        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> [new caption]")

        name = args[1].lower()
        new_caption = args[2] if len(args) == 3 else None
        file_id = message.reply_to_message.photo.file_id

        update_data = {"file_id": file_id}
        if new_caption:
            update_data["caption"] = new_caption

        result = flyer_collection.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": update_data}
        )

        if result.matched_count:
            await message.reply(f"✅ Flyer '{name}' updated.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ Only admins can schedule flyers.")

        match = re.match(r"/scheduleflyer (\w+)\s+(\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2})\s+(.+)", message.text)
        if not match:
            return await message.reply("❌ Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <target_group_id_or_shortcut>")

        name, dt_str, target = match.groups()

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("❌ Invalid datetime format. Use YYYY-MM-DD HH:MM.")

        target_id = GROUP_SHORTCUTS.get(target.upper(), None)
        if target_id is None:
            try:
                target_id = int(target)
            except ValueError:
                return await message.reply("❌ Invalid group ID or shortcut.")

        job_id = f"{message.chat.id}_{name}_{dt.timestamp()}"

        async def post_flyer():
            await client.send_photo(chat_id=target_id, photo=flyer["file_id"], caption=flyer["caption"])
            scheduled_jobs.delete_one({"job_id": job_id})

        scheduler.add_job(post_flyer, "date", run_date=dt)
        scheduled_jobs.insert_one({
            "job_id": job_id,
            "chat_id": message.chat.id,
            "name": name,
            "target_id": target_id,
            "time": dt
        })

        await message.reply(f"📆 Flyer '{name}' scheduled for {dt} in {target}.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduled_jobs.find({"chat_id": message.chat.id})
        lines = []
        for job in jobs:
            time = job["time"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"- {job['name']} → {job['target_id']} at {time}")

        if not lines:
            return await message.reply("📭 No flyers scheduled.")

        await message.reply("📆 Scheduled Flyers:\n" + "\n".join(lines))

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            return await message.reply("❌ Usage: /canceljob <flyer_name>")

        name = args[1].lower()
        jobs = scheduled_jobs.find({"chat_id": message.chat.id, "name": name})

        count = 0
        for job in jobs:
            scheduler.remove_job(job["job_id"])
            scheduled_jobs.delete_one({"job_id": job["job_id"]})
            count += 1

        if count:
            await message.reply(f"❌ Canceled {count} scheduled jobs for '{name}'.")
        else:
            await message.reply("❌ No matching jobs found.")
