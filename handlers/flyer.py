from pyrogram import Client, filters
from pyrogram.types import Message
import json
import os
from utils.decorators import admin_only
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from datetime import datetime, timedelta

FLYER_FILE = "data/flyers.json"
scheduler = BackgroundScheduler(timezone=timezone("America/Los_Angeles"))
scheduler.start()

flyers = {}
if os.path.exists(FLYER_FILE):
    with open(FLYER_FILE, "r") as f:
        flyers = json.load(f)


def save_flyers():
    with open(FLYER_FILE, "w") as f:
        json.dump(flyers, f, indent=4)


@Client.on_message(filters.command("addflyer") & filters.group)
@admin_only
async def add_flyer(client, message: Message):
    if not message.photo or not message.caption or len(message.caption.split(maxsplit=1)) < 2:
        return await message.reply("Usage:\nSend image with caption:\n<code>/addflyer FlyerName Caption...</code>")

    args = message.caption.split(maxsplit=1)
    flyer_name = args[0].replace("/addflyer", "").strip().lower()
    caption = args[1].strip()

    chat_id = str(message.chat.id)
    if chat_id not in flyers:
        flyers[chat_id] = {}

    flyers[chat_id][flyer_name] = {
        "file_id": message.photo.file_id,
        "caption": caption
    }
    save_flyers()
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> saved with caption.")


@Client.on_message(filters.command("flyer") & filters.group)
async def get_flyer(client, message: Message):
    if not message.text or len(message.text.split(maxsplit=1)) < 2:
        return await message.reply("Usage:\n<code>/flyer FlyerName</code>")

    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)

    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply(f"No flyer named <b>{flyer_name}</b> found.")

    flyer = flyers[chat_id][flyer_name]
    await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))


@Client.on_message(filters.command("listflyers") & filters.group)
async def list_flyers(client, message: Message):
    chat_id = str(message.chat.id)
    if chat_id not in flyers or not flyers[chat_id]:
        return await message.reply("No flyers added yet.")
    flyer_list = "\n".join(f"• <code>{name}</code>" for name in flyers[chat_id])
    await message.reply(f"📌 Flyers:\n\n{flyer_list}")


@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def delete_flyer(client, message: Message):
    if not message.text or len(message.text.split(maxsplit=1)) < 2:
        return await message.reply("Usage:\n<code>/deleteflyer FlyerName</code>")
    flyer_name = message.text.split(maxsplit=1)[1].strip().lower()
    chat_id = str(message.chat.id)
    if chat_id not in flyers or flyer_name not in flyers[chat_id]:
        return await message.reply("Flyer not found.")
    del flyers[chat_id][flyer_name]
    save_flyers()
    await message.reply(f"🗑️ Flyer <b>{flyer_name}</b> deleted.")


def post_flyer_job(client: Client, flyer_data, target_chat):
    async def job():
        await client.send_photo(
            chat_id=target_chat,
            photo=flyer_data["file_id"],
            caption=flyer_data.get("caption", "")
        )
    return job


@Client.on_message(filters.command("scheduleflyer") & filters.group)
@admin_only
async def schedule_flyer(client, message: Message):
    try:
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply("Usage:\n<code>/scheduleflyer FlyerName TargetGroupID HH:MM AM/PM</code>")
        flyer_name = args[1].strip().lower()
        target_chat = args[2]
        time_str = f"{args[3]} {args[4].upper()}"

        schedule_time = datetime.strptime(time_str, "%I:%M %p").time()

        chat_id = str(message.chat.id)
        if chat_id not in flyers or flyer_name not in flyers[chat_id]:
            return await message.reply("Flyer not found in this group.")

        flyer_data = flyers[chat_id][flyer_name]
        now = datetime.now(timezone("America/Los_Angeles"))
        run_time = datetime.combine(now.date(), schedule_time)
        if run_time < now:
            run_time += timedelta(days=1)

        scheduler.add_job(post_flyer_job(client, flyer_data, int(target_chat)), trigger="date", run_date=run_time)

        await message.reply(f"⏰ Flyer <b>{flyer_name}</b> scheduled for <code>{run_time.strftime('%I:%M %p')}</code> in <code>{target_chat}</code>.")
    except Exception as e:
        await message.reply(f"Error: <code>{e}</code>")
