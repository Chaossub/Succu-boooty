import os
from datetime import datetime
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.check_admin import is_admin

MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]
scheduled = db["scheduled_flyers"]
flyers = db["flyers"]

# Posts flyer at the right time
async def post_scheduled_flyer(app, chat_id, flyer_name):
    flyer = flyers.find_one({"chat_id": chat_id, "name": flyer_name})
    if not flyer:
        return
    if flyer.get("photo_id"):
        await app.send_photo(chat_id, flyer["photo_id"], caption=flyer.get("caption", ""))
    else:
        await app.send_message(chat_id, flyer.get("caption", ""))

async def scheduleflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.text.split(None, 4)
    if len(args) < 5:
        return await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <repeat> (group is this chat)"
        )
    _, flyer_name, date_str, time_str, repeat = args
    flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name.lower()})
    if not flyer:
        return await message.reply("❌ No flyer by that name.")

    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except Exception as e:
        return await message.reply("❌ Invalid datetime format. Use YYYY-MM-DD HH:MM.")

    doc = {
        "chat_id": message.chat.id,
        "flyer_name": flyer_name.lower(),
        "run_time": dt,
        "repeat": repeat,
        "created_by": message.from_user.id
    }
    result = scheduled.insert_one(doc)
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> scheduled for <b>{dt}</b> ({repeat})\nID: <code>{str(result.inserted_id)}</code>")

async def listscheduled_handler(client, message: Message):
    scheds = list(scheduled.find({"chat_id": message.chat.id}))
    if not scheds:
        return await message.reply("No scheduled flyers.")
    lines = [
        f"ID: <code>{str(doc['_id'])}</code> | {doc['flyer_name']} | {doc['run_time'].strftime('%Y-%m-%d %H:%M')} ({doc.get('repeat','once')})"
        for doc in scheds
    ]
    await message.reply("🗓️ <b>Scheduled Flyers:</b>\n" + "\n".join(lines))

async def cancelscheduled_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /cancelscheduled <id>")
    _id = args[1]
    from bson import ObjectId
    result = scheduled.delete_one({"_id": ObjectId(_id)})
    if result.deleted_count:
        await message.reply("✅ Scheduled post cancelled.")
    else:
        await message.reply("❌ No scheduled post by that ID.")

def restore_jobs(app, scheduler: AsyncIOScheduler):
    # Loads scheduled jobs from Mongo on startup
    from bson import ObjectId
    jobs = list(scheduled.find({}))
    for job in jobs:
        run_time = job["run_time"]
        chat_id = job["chat_id"]
        flyer_name = job["flyer_name"]
        scheduler.add_job(
            post_scheduled_flyer,
            "date",
            run_date=run_time,
            args=[app, chat_id, flyer_name],
            id=str(job["_id"])
        )

def register(app, scheduler):
    app.add_handler(filters.command("scheduleflyer") & filters.group, scheduleflyer_handler)
    app.add_handler(filters.command("listscheduled") & filters.group, listscheduled_handler)
    app.add_handler(filters.command("cancelscheduled") & filters.group, cancelscheduled_handler)
    restore_jobs(app, scheduler)
