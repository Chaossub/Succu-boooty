import os
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler
from utils.mongo import flyer_collection, scheduled_jobs
from utils.check_admin import is_admin
from utils.groups import GROUP_SHORTCUTS
from datetime import datetime
import pytz

def register(app: Client, scheduler: BackgroundScheduler):
    
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can add flyers.")

        args = message.text.split(None, 2)
        if len(args) < 3:
            return await message.reply("⚠️ Usage:\n<code>/addflyer name caption</code> (with photo attached)")

        flyer_name = args[1].lower()
        caption = args[2]

        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo[-1].file_id
        else:
            return await message.reply("❌ Please send or reply to a photo.")

        flyer_collection.update_one(
            {"chat_id": chat_id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{flyer_name}' saved!")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client: Client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage:\n<code>/flyer name</code>")
        
        flyer_name = args[1].lower()
        chat_id = message.chat.id
        flyer = flyer_collection.find_one({"chat_id": chat_id, "name": flyer_name})

        if not flyer:
            return await message.reply("❌ Flyer not found.")

        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client: Client, message: Message):
        chat_id = message.chat.id
        flyers = list(flyer_collection.find({"chat_id": chat_id}))

        if not flyers:
            return await message.reply("📂 No flyers saved.")
        
        flyer_list = "\n".join(f"• <b>{f['name']}</b>" for f in flyers)
        await message.reply(f"📂 Saved Flyers:\n{flyer_list}")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")

        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage:\n<code>/deleteflyer name</code>")

        flyer_name = args[1].lower()
        result = flyer_collection.delete_one({"chat_id": chat_id, "name": flyer_name})

        if result.deleted_count == 0:
            return await message.reply("❌ Flyer not found.")
        await message.reply(f"🗑️ Flyer '{flyer_name}' deleted.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can change flyers.")

        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage:\n<code>/changeflyer name</code> (with photo)")

        flyer_name = args[1].lower()

        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo[-1].file_id
        else:
            return await message.reply("❌ Please send or reply to a photo.")

        result = flyer_collection.update_one(
            {"chat_id": chat_id, "name": flyer_name},
            {"$set": {"file_id": file_id}},
        )

        if result.matched_count == 0:
            return await message.reply("❌ Flyer not found.")
        await message.reply(f"🔄 Flyer '{flyer_name}' image updated.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can schedule flyers.")

        args = message.text.split(None, 4)
        if len(args) < 4:
            return await message.reply(
                "⚠️ Usage:\n<code>/scheduleflyer name YYYY-MM-DD HH:MM target_group</code>\nExample: <code>/scheduleflyer myflyer 2025-07-10 18:30 TEST_GROUP</code>"
            )

        flyer_name = args[1].lower()
        date_str = args[2]
        time_str = args[3]
        target_group_key = args[4].upper()

        group_id = GROUP_SHORTCUTS.get(target_group_key)
        if not group_id:
            return await message.reply("❌ Unknown target group shortcut.")

        flyer = flyer_collection.find_one({"chat_id": chat_id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        try:
            tz = pytz.timezone(os.environ.get("SCHEDULER_TZ", "UTC"))
            run_time = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
        except ValueError:
            return await message.reply("❌ Invalid date or time format. Use YYYY-MM-DD HH:MM")

        job_id = f"{chat_id}_{flyer_name}_{run_time.timestamp()}"
        scheduler.add_job(
            send_scheduled_flyer,
            "date",
            run_date=run_time,
            args=[client, group_id, flyer["file_id"], flyer["caption"]],
            id=job_id,
        )

        scheduled_jobs.insert_one({
            "job_id": job_id,
            "chat_id": chat_id,
            "flyer_name": flyer_name,
            "target_group": group_id,
            "run_time": run_time.isoformat()
        })

        await message.reply(f"📅 Flyer '{flyer_name}' scheduled for {run_time.strftime('%Y-%m-%d %H:%M')} in {target_group_key}.")

    async def send_scheduled_flyer(client: Client, target_chat_id: int, file_id: str, caption: str):
        try:
            await client.send_photo(chat_id=target_chat_id, photo=file_id, caption=caption)
        except Exception as e:
            print(f"[Scheduler Error] Failed to send flyer: {e}")
