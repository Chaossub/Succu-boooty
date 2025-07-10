import os
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message, InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from utils.mongo import flyer_collection, scheduled_jobs
from utils.check_admin import is_admin
from utils.groups import GROUP_SHORTCUTS

def register(app, scheduler: BackgroundScheduler):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message: Message):
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
            upsert=True
        )
        await message.reply(f"✅ Flyer <b>{flyer_name}</b> saved.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage: /flyer name")

        flyer_name = args[1].lower()
        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": flyer_name})

        if not flyer:
            return await message.reply("❌ Flyer not found.")

        await client.send_photo(
            chat_id=message.chat.id,
            photo=flyer["file_id"],
            caption=flyer.get("caption", "")
        )

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = flyer_collection.find({"chat_id": message.chat.id})
        names = [f"• {f['name']}" for f in flyers]

        if not names:
            return await message.reply("📂 No flyers saved.")
        await message.reply("📂 Saved Flyers:\n" + "\n".join(names))

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage: /deleteflyer name")

        result = flyer_collection.delete_one({"chat_id": message.chat.id, "name": args[1].lower()})
        if result.deleted_count:
            await message.reply("✅ Flyer deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        args = message.text.split(None, 2)
        if len(args) < 2:
            return await message.reply("⚠️ Usage: /changeflyer name [new caption] (reply to new image)")

        flyer_name = args[1].lower()
        new_caption = args[2] if len(args) > 2 else None

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        update = {}
        if message.reply_to_message and message.reply_to_message.photo:
            update["file_id"] = message.reply_to_message.photo[-1].file_id
        if new_caption:
            update["caption"] = new_caption

        if not update:
            return await message.reply("❌ No updates provided.")

        flyer_collection.update_one({"chat_id": message.chat.id, "name": flyer_name}, {"$set": update})
        await message.reply("✅ Flyer updated.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        args = message.text.split(None, 3)
        if len(args) < 4:
            return await message.reply("⚠️ Usage:\n<code>/scheduleflyer name yyyy-mm-dd HH:MM group</code>")

        flyer_name = args[1].lower()
        time_str = args[2]
        group_key = args[3].strip().upper()

        target_chat_id = os.environ.get(group_key)
        if not target_chat_id:
            return await message.reply("❌ Invalid group shortcut.")

        flyer = flyer_collection.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")

        try:
            scheduled_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply("❌ Invalid time format. Use yyyy-mm-dd HH:MM")

        job_id = f"{message.chat.id}_{flyer_name}_{scheduled_time.isoformat()}"

        async def send_scheduled_flyer():
            await client.send_photo(
                chat_id=int(target_chat_id),
                photo=flyer["file_id"],
                caption=flyer.get("caption", "")
            )

        scheduler.add_job(
            send_scheduled_flyer,
            trigger="date",
            run_date=scheduled_time,
            id=job_id
        )

        scheduled_jobs.insert_one({
            "job_id": job_id,
            "flyer_name": flyer_name,
            "from_chat": message.chat.id,
            "to_chat": int(target_chat_id),
            "scheduled_time": scheduled_time.isoformat()
        })

        await message.reply(f"📅 Scheduled flyer <b>{flyer_name}</b> to post in <b>{group_key}</b> at {time_str}.")

    @app.on_message(filters.command("canceljob") & filters.group)
    async def cancel_job(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return

        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("⚠️ Usage: /canceljob <job_id>")

        job_id = args[1]
        scheduler.remove_job(job_id)
        scheduled_jobs.delete_one({"job_id": job_id})
        await message.reply("✅ Scheduled post cancelled.")

    @app.on_message(filters.command("listjobs") & filters.group)
    async def list_jobs(client, message: Message):
        jobs = scheduled_jobs.find({"from_chat": message.chat.id})
        if jobs.count() == 0:
            return await message.reply("📭 No scheduled jobs.")

        lines = []
        for job in jobs:
            lines.append(f"• {job['flyer_name']} → {job['to_chat']} at {job['scheduled_time']}\nID: <code>{job['job_id']}</code>")

        await message.reply("📅 Scheduled Flyers:\n" + "\n".join(lines), disable_web_page_preview=True)
