import os
from datetime import datetime
from pyrogram import filters, Client
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from pyrogram.types import Message
from builtins import mongo_client as client
from config import MONGO_DB

db = client[MONGO_DB]
flyer_col = db["flyers"]
schedule_col = db["scheduled_flyers"]

SCHED_TZ = timezone("America/Los_Angeles")

@Client.on_message(filters.command("addflyer") & filters.group & filters.photo)
async def add_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /addflyer <name> <caption>")

    try:
        args = message.text.split(None, 2)
        name = args[1].lower()
        caption = args[2] if len(args) > 2 else ""

        flyer = {
            "name": name,
            "caption": caption,
            "file_id": message.photo.file_id,
            "group_id": message.chat.id
        }

        flyer_col.replace_one(
            {"name": name, "group_id": message.chat.id},
            flyer,
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' added.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("flyer") & filters.group)
async def send_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /flyer <name>")

    name = message.command[1].lower()
    flyer = flyer_col.find_one({"name": name, "group_id": message.chat.id})
    if flyer:
        await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
    else:
        await message.reply("❌ Flyer not found.")

@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    flyers = list(flyer_col.find({"group_id": message.chat.id}))
    if not flyers:
        return await message.reply("No flyers found.")
    text = "📌 Flyers:

" + "\n".join(f"- {f['name']}" for f in flyers)
    await message.reply(text)

@Client.on_message(filters.command("deleteflyer") & filters.group)
async def delete_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /deleteflyer <name>")

    name = message.command[1].lower()
    result = flyer_col.delete_one({"name": name, "group_id": message.chat.id})
    if result.deleted_count:
        await message.reply(f"🗑️ Flyer '{name}' deleted.")
    else:
        await message.reply("❌ Flyer not found.")

@Client.on_message(filters.command("changeflyer") & filters.group & filters.reply)
async def change_flyer(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /changeflyer <name> (reply with new image)")

    if not message.reply_to_message.photo:
        return await message.reply("❌ Please reply to a new photo.")

    name = message.command[1].lower()
    updated = flyer_col.update_one(
        {"name": name, "group_id": message.chat.id},
        {"$set": {"file_id": message.reply_to_message.photo.file_id}}
    )
    if updated.modified_count:
        await message.reply(f"✅ Flyer '{name}' updated.")
    else:
        await message.reply("❌ Flyer not found.")

@Client.on_message(filters.command("scheduleflyer") & filters.group)
async def schedule_flyer(client, message: Message):
    if len(message.command) < 4:
        return await message.reply("Usage: /scheduleflyer <name> <HH:MM> <target_group_id>")

    name = message.command[1].lower()
    time_str = message.command[2]
    target_group = int(message.command[3])

    flyer = flyer_col.find_one({"name": name, "group_id": message.chat.id})
    if not flyer:
        return await message.reply("❌ Flyer not found in this group.")

    try:
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(SCHED_TZ)
        run_time = SCHED_TZ.localize(datetime(now.year, now.month, now.day, hour, minute))

        job_id = f"{name}_{message.chat.id}_{target_group}_{time_str}"
        schedule_col.insert_one({
            "job_id": job_id,
            "source_group": message.chat.id,
            "target_group": target_group,
            "name": name,
            "caption": flyer["caption"],
            "file_id": flyer["file_id"],
            "time_str": time_str
        })

        scheduler.add_job(
            send_scheduled_flyer,
            trigger="cron",
            hour=hour,
            minute=minute,
            timezone=SCHED_TZ,
            args=[client, flyer["file_id"], flyer["caption"], target_group],
            id=job_id,
            replace_existing=True
        )

        await message.reply(f"✅ Scheduled flyer '{name}' to post daily at {time_str} in group {target_group}.")
    except Exception as e:
        await message.reply(f"❌ Failed to schedule flyer: {e}")

async def send_scheduled_flyer(client, file_id, caption, group_id):
    await client.send_photo(group_id, file_id, caption=caption)

def register(app, scheduler: BackgroundScheduler):
    app.add_handler(add_flyer)
    app.add_handler(send_flyer)
    app.add_handler(list_flyers)
    app.add_handler(delete_flyer)
    app.add_handler(change_flyer)
    app.add_handler(schedule_flyer)

