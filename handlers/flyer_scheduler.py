import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

OWNER_ID = 6964994611  # <--- your Telegram user ID

# Admin/owner check
async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
scheduled = mongo.scheduled_flyers

def send_scheduled_flyer(app, chat_id, flyer):
    # Used by scheduler (no await)
    try:
        if "file_id" in flyer:
            app.send_photo(chat_id, flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            app.send_message(chat_id, flyer.get("caption", ""))
    except Exception as e:
        print("Scheduled flyer failed:", e)

# /scheduleflyer flyername YYYY-MM-DD HH:MM (Los Angeles time, 24h) [optional chat_id]
async def scheduleflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can schedule flyers.")
    args = message.text.split()
    if len(args) < 4:
        return await message.reply("Usage: /scheduleflyer flyername YYYY-MM-DD HH:MM")
    flyer_name = args[1].lower()
    date_str = args[2]
    time_str = args[3]
    flyer = scheduled.find_one({"chat_id": message.chat.id, "name": flyer_name})
    if not flyer:
        flyer = mongo.flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
    if not flyer:
        return await message.reply("❌ Flyer not found in this group.")
    # Parse time (assume America/Los_Angeles by default)
    tz = pytz.timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
    try:
        when = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
    except Exception:
        return await message.reply("❌ Invalid date/time format. Use YYYY-MM-DD HH:MM (24h, LA time).")
    # Store schedule in db
    sched_job = {
        "chat_id": message.chat.id,
        "name": flyer_name,
        "when": when.isoformat(),
        "file_id": flyer.get("file_id"),
        "caption": flyer.get("caption", ""),
    }
    scheduled.insert_one(sched_job)
    await message.reply(f"✅ Scheduled flyer <b>{flyer_name}</b> for <b>{when.strftime('%Y-%m-%d %H:%M')}</b>!")

# /listschedules - admin only
async def listschedules_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can view scheduled flyers.")
    results = scheduled.find({"chat_id": message.chat.id})
    msg = []
    for f in results:
        msg.append(f"<b>{f['name']}</b> at <code>{f['when']}</code>")
    if not msg:
        return await message.reply("No flyers scheduled.")
    await message.reply("\n".join(msg))

# /deleteschedule flyername - admin only
async def deleteschedule_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete scheduled flyers.")
    if len(message.command) < 2:
        return await message.reply("Usage: /deleteschedule flyername")
    name = message.command[1].lower()
    res = scheduled.delete_one({"chat_id": message.chat.id, "name": name})
    if res.deleted_count:
        await message.reply(f"🗑️ Deleted scheduled flyer <b>{name}</b>.")
    else:
        await message.reply("❌ No scheduled flyer found by that name.")

# /showschedule flyername (anyone)
async def showschedule_handler(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: /showschedule flyername")
    name = message.command[1].lower()
    flyer = scheduled.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("❌ No scheduled flyer found.")
    cap = f"Flyer <b>{flyer['name']}</b> will be sent at <code>{flyer['when']}</code>."
    if "file_id" in flyer:
        await message.reply_photo(flyer["file_id"], caption=cap)
    else:
        await message.reply(cap)

def restore_jobs(app, scheduler):
    tz = pytz.timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
    for flyer in scheduled.find():
        try:
            when = datetime.fromisoformat(flyer["when"])
            scheduler.add_job(
                send_scheduled_flyer,
                "date",
                run_date=when,
                args=[app, flyer["chat_id"], flyer],
                misfire_grace_time=60 * 60,
            )
        except Exception as e:
            print(f"[restore_jobs] Skipping {flyer['name']} ({e})")

def register(app, scheduler):
    app.add_handler(filters.command("scheduleflyer")(scheduleflyer_handler))
    app.add_handler(filters.command("listschedules")(listschedules_handler))
    app.add_handler(filters.command("deleteschedule")(deleteschedule_handler))
    app.add_handler(filters.command("showschedule")(showschedule_handler))
    restore_jobs(app, scheduler)
    print("Scheduled flyer handler loaded.")

