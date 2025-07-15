# handlers/flyer.py

import os
import logging
import pytz
import tzlocal
from datetime import datetime, time as dtime, timedelta
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message
from apscheduler.schedulers.background import BackgroundScheduler

# Logging
logger = logging.getLogger(__name__)

# Mongo
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo["flyers"]
schedule_col = mongo["flyer_schedules"]

# Group aliases from env
ALIASES = {
    "MODELS_CHAT": int(os.environ["MODELS_CHAT"]),
    "TEST_GROUP": int(os.environ["TEST_GROUP"]),
    "SUCCUBUS_SANCTUARY": int(os.environ["SUCCUBUS_SANCTUARY"]),
}

# Permissions (hardcoded superadmin)
SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def get_timezone():
    tz_name = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
    return pytz.timezone(tz_name)

def flyer_to_caption(f):
    cap = f.get("caption", "")
    if f.get("type") == "text":
        cap = f"<b>{f['name']}</b>\n{cap}"
    return cap

def register(app: Client, scheduler: BackgroundScheduler):
    logger.info("📢 flyer.register() called")
    print(f"Scheduler running in TZ: {get_timezone()}")
    print(f"ALIASES: {ALIASES}")

    async def post_flyer_job(flyer_id, chat_id):
        f = flyers_col.find_one({"_id": flyer_id})
        if not f:
            logger.warning(f"Flyer {flyer_id} missing at schedule time")
            return
        try:
            if f["type"] == "photo":
                await app.send_photo(chat_id, f["file_id"], caption=flyer_to_caption(f))
            else:
                await app.send_message(chat_id, flyer_to_caption(f))
            logger.info(f"✅ Posted flyer '{f['name']}' to {chat_id}")
        except Exception as e:
            logger.error(f"Failed posting flyer: {e}")

    def schedule_flyer_post(flyer_id, chat_id, when, job_type="once"):
        job_id = f"flyer_{flyer_id}_{chat_id}_{when.timestamp()}"
        def _wrapper():
            app.loop.create_task(post_flyer_job(flyer_id, chat_id))
            if job_type == "once":
                try: scheduler.remove_job(job_id)
                except: pass
        scheduler.add_job(
            _wrapper,
            'date' if job_type == "once" else 'cron',
            run_date=when if job_type == "once" else None,
            id=job_id,
            replace_existing=True,
            timezone=get_timezone()
        )

    # /addflyer <name> <caption> (with or without image)
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message: Message):
        user_id = message.from_user.id
        if not await is_admin(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can add flyers.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption> (send with or without photo)")
        name = args[1].strip().lower()
        caption = args[2].strip()
        if flyers_col.find_one({"name": name}):
            return await message.reply("❌ Flyer already exists.")
        # Check for photo
        if message.photo:
            file_id = message.photo.file_id
            flyer = {"name": name, "type": "photo", "file_id": file_id, "caption": caption}
            flyers_col.insert_one(flyer)
            await message.reply(f"✅ Image flyer '{name}' added.")
        else:
            flyer = {"name": name, "type": "text", "caption": caption}
            flyers_col.insert_one(flyer)
            await message.reply(f"✅ Text flyer '{name}' added.")

    # /flyer <name>
    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = args[1].strip().lower()
        f = flyers_col.find_one({"name": name})
        if not f:
            return await message.reply("❌ Flyer not found.")
        if f["type"] == "photo":
            await message.reply_photo(f["file_id"], caption=flyer_to_caption(f))
        else:
            await message.reply(flyer_to_caption(f))

    # /listflyers
    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message: Message):
        flyers = list(flyers_col.find())
        if not flyers:
            return await message.reply("No flyers saved.")
        out = "\n".join([f"- <b>{f['name']}</b>" for f in flyers])
        await message.reply(f"<b>Saved Flyers:</b>\n{out}")

    # /deleteflyer <name>
    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message: Message):
        user_id = message.from_user.id
        if not await is_admin(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1].strip().lower()
        flyers_col.delete_one({"name": name})
        await message.reply(f"🗑 Deleted flyer '{name}'.")

    # /scheduleflyer <name> <group_alias> <HH:MM> [once|daily]
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        user_id = message.from_user.id
        if not await is_admin(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can schedule flyers.")
        args = message.text.split(maxsplit=4)
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <group_alias> <HH:MM> [once|daily]")
        name = args[1].strip().lower()
        group_alias = args[2].strip().upper()
        hhmm = args[3]
        mode = args[4].lower() if len(args) > 4 else "once"
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if group_alias not in ALIASES:
            return await message.reply(f"❌ Unknown group alias: {group_alias}")
        # Parse time
        try:
            hour, minute = map(int, hhmm.split(":"))
        except:
            return await message.reply("❌ Invalid time format (use HH:MM).")
        tz = get_timezone()
        now = datetime.now(tz)
        target_time = tz.localize(datetime.combine(now.date(), dtime(hour, minute)))
        if target_time < now:
            target_time += timedelta(days=1)
        chat_id = ALIASES[group_alias]
        doc = {
            "flyer_id": flyer["_id"],
            "chat_id": chat_id,
            "time": target_time,
            "mode": mode,
        }
        schedule_col.insert_one(doc)
        schedule_flyer_post(flyer["_id"], chat_id, target_time, job_type=mode)
        await message.reply(f"✅ Scheduled flyer '{name}' to {group_alias} at {hhmm} ({mode}).\nTime zone: {tz}")

    # /listscheduled
    @app.on_message(filters.command("listscheduled") & filters.group)
    async def list_scheduled(client, message: Message):
        schedules = list(schedule_col.find())
        if not schedules:
            return await message.reply("No scheduled flyers.")
        out = []
        for s in schedules:
            flyer = flyers_col.find_one({"_id": s["flyer_id"]})
            group_name = [k for k,v in ALIASES.items() if v == s["chat_id"]]
            group_alias = group_name[0] if group_name else str(s["chat_id"])
            out.append(f"- <b>{flyer['name']}</b> to {group_alias} at {s['time'].strftime('%H:%M')} ({s['mode']})")
        await message.reply("<b>Scheduled Flyers:</b>\n" + "\n".join(out))

    # /cancelflyer <flyer_name>
    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancelflyer_handler(client, message: Message):
        user_id = message.from_user.id
        if not await is_admin(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <flyer_name>")
        name = args[1].strip().lower()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        schedule_col.delete_many({"flyer_id": flyer["_id"]})
        await message.reply(f"🗑 Canceled scheduled posts for '{name}'.")

    # /changeflyer <name> (reply with photo)
    @app.on_message(filters.command("changeflyer") & filters.group & filters.reply)
    async def changeflyer_handler(client, message: Message):
        user_id = message.from_user.id
        if not await is_admin(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can update flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> (reply to new image)")
        name = args[1].strip().lower()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Reply to a new photo with /changeflyer <name>.")
        file_id = message.reply_to_message.photo.file_id
        flyers_col.update_one({"_id": flyer["_id"]}, {"$set": {"file_id": file_id, "type": "photo"}})
        await message.reply(f"✅ Updated flyer '{name}' image.")

