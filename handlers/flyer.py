import os
from datetime import datetime
from pytz import timezone
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from config import MONGO_URI
from utils.decorators import admin_only

client = MongoClient(MONGO_URI)
db = client["succubot"]
flyers = db["flyers"]

LA_TZ = timezone("America/Los_Angeles")


def register(app: Client, scheduler: BackgroundScheduler):
    app.add_handler(filters.command("addflyer") & filters.group, add_flyer)
    app.add_handler(filters.command("changeflyer") & filters.group, change_flyer)
    app.add_handler(filters.command("deleteflyer") & filters.group, delete_flyer)
    app.add_handler(filters.command("flyer") & filters.group, get_flyer)
    app.add_handler(filters.command("flyerlist") & filters.group, flyer_list)
    app.add_handler(filters.command("scheduleflyer") & filters.group, schedule_flyer)
    scheduler.add_jobstore("mongodb", collection="flyer_jobs", database="succubot", client=client)
    scheduler.start()


@Client.on_message(filters.command("addflyer") & filters.group)
@admin_only
async def add_flyer(client, message: Message):
    if not message.photo:
        return await message.reply("Please attach a photo when adding a flyer.")

    try:
        _, name_caption = message.text.split(maxsplit=1)
        name, caption = name_caption.split(" ", 1)
    except ValueError:
        return await message.reply("Usage: /addflyer <name> <caption> (with photo)")

    file_id = message.photo.file_id
    flyers.update_one(
        {"group_id": message.chat.id, "name": name.lower()},
        {"$set": {"caption": caption, "file_id": file_id}},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' saved!")


@Client.on_message(filters.command("changeflyer") & filters.group)
@admin_only
async def change_flyer(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply("Reply to a new image with /changeflyer <name>")

    try:
        _, name = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Usage: /changeflyer <name> (as reply to photo)")

    file_id = message.reply_to_message.photo.file_id
    updated = flyers.update_one(
        {"group_id": message.chat.id, "name": name.lower()},
        {"$set": {"file_id": file_id}}
    )

    if updated.matched_count:
        await message.reply(f"✅ Flyer '{name}' image updated!")
    else:
        await message.reply("❌ Flyer not found.")


@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer(client, message: Message):
    try:
        _, name = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Usage: /deleteflyer <name>")

    deleted = flyers.delete_one({"group_id": message.chat.id, "name": name.lower()})
    if deleted.deleted_count:
        await message.reply(f"🗑️ Flyer '{name}' deleted.")
    else:
        await message.reply("❌ Flyer not found.")


@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    try:
        _, name = message.text.split(maxsplit=1)
    except ValueError:
        return await message.reply("Usage: /flyer <name>")

    flyer = flyers.find_one({"group_id": message.chat.id, "name": name.lower()})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    await message.reply_photo(photo=flyer["file_id"], caption=flyer["caption"])


@Client.on_message(filters.command("flyerlist") & filters.group)
@admin_only
async def flyer_list(client, message: Message):
    group_id = message.chat.id
    flyer_docs = flyers.find({"group_id": group_id})
    names = [doc["name"] for doc in flyer_docs]

    if not names:
        return await message.reply("No flyers have been added in this group.")

    name_list = "\n".join(f"• {name}" for name in names)
    await message.reply(f"📌 Flyers for this group:\n\n{name_list}")


@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer(client, message: Message):
    try:
        _, flyer_name, time_str, target_group = message.text.split()
        target_group = int(target_group)
    except ValueError:
        return await message.reply("Usage: /scheduleflyer <flyer_name> <HH:MM> <target_group_id>")

    flyer = flyers.find_one({"group_id": message.chat.id, "name": flyer_name.lower()})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    try:
        post_time = datetime.strptime(time_str, "%H:%M")
        now = datetime.now(LA_TZ)
        run_time = LA_TZ.localize(datetime(now.year, now.month, now.day, post_time.hour, post_time.minute))
        if run_time < now:
            run_time = run_time.replace(day=now.day + 1)
    except Exception:
        return await message.reply("❌ Invalid time format. Use HH:MM in 24h format (e.g., 18:30)")

    scheduler = message._client.scheduler
    scheduler.add_job(
        send_scheduled_flyer,
        "date",
        run_date=run_time,
        args=[client, target_group, flyer["file_id"], flyer["caption"]],
        id=f"{flyer_name}_{target_group}_{run_time}"
    )

    await message.reply(f"✅ Flyer '{flyer_name}' scheduled to post at {time_str} in group {target_group}.")


async def send_scheduled_flyer(client, target_group, file_id, caption):
    try:
        await client.send_photo(chat_id=target_group, photo=file_id, caption=caption)
    except Exception as e:
        print(f"Failed to send scheduled flyer: {e}")
