import os
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DBNAME")
client = MongoClient(MONGO_URI)
db = client[MONGO_DBNAME]
flyers = db.flyers

GROUP_ALIASES = {
    "MODELS_CHAT": int(os.getenv("MODELS_CHAT")),
    "TEST_GROUP": int(os.getenv("TEST_GROUP")),
    "SUCCUBUS_SANCTUARY": int(os.getenv("SUCCUBUS_SANCTUARY")),
}

SUPER_ADMIN_ID = 6964994611

def get_group_id(alias_or_id):
    try:
        return GROUP_ALIASES[alias_or_id]
    except KeyError:
        try:
            return int(alias_or_id)
        except Exception:
            return None

def is_admin(client: Client, chat_id: int, user_id: int):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        m = client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def register(app: Client, scheduler):
    async def ensure_admin(message: Message):
        return message.from_user.id == SUPER_ADMIN_ID or (
            await app.get_chat_member(message.chat.id, message.from_user.id)
        ).status in ("administrator", "creator")

    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can add flyers.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption> (send with photo or just text)")
        name, caption = args[1], args[2]
        flyer_data = {
            "name": name,
            "caption": caption,
            "type": "text",
            "owner": message.from_user.id,
        }
        if message.photo:
            flyer_data["type"] = "photo"
            flyer_data["file_id"] = message.photo.file_id
        flyers.update_one({"name": name}, {"$set": flyer_data}, upsert=True)
        await message.reply(f"✅ {'Photo' if message.photo else 'Text'} flyer '{name}' added.")

    @app.on_message(filters.command("listflyers"))
    async def list_flyers(client, message):
        all_flyers = list(flyers.find({}, {"_id": 0, "name": 1, "type": 1}))
        if not all_flyers:
            return await message.reply("No flyers found.")
        msg = "Flyers:\n" + "\n".join(f"- <b>{f['name']}</b> ({f['type']})" for f in all_flyers)
        await message.reply(msg)

    @app.on_message(filters.command("flyer"))
    async def get_flyer(client, message):
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = args[1]
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer["type"] == "photo":
            await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

    @app.on_message(filters.command("deleteflyer"))
    async def delete_flyer(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1]
        flyers.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    @app.on_message(filters.command("changeflyer"))
    async def change_flyer(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can change flyers.")
        args = message.text.split()
        if len(args) < 2 or not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Usage: reply to a new photo with /changeflyer <name>")
        name = args[1]
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        flyers.update_one({"name": name}, {"$set": {
            "file_id": message.reply_to_message.photo.file_id,
            "type": "photo",
        }})
        await message.reply(f"✅ Updated flyer '{name}' image.")

    def schedule_flyer_post(group_id, flyer_name, when, freq, job_id=None):
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            log.error(f"Flyer '{flyer_name}' not found for scheduled post!")
            return
        async def _job():
            try:
                log.info(f"Trying to post flyer '{flyer_name}' to {group_id} (type: {type(group_id)})")
                if flyer["type"] == "photo":
                    await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
                else:
                    await app.send_message(group_id, flyer.get("caption", ""))
            except Exception as e:
                log.error(f"Failed to post flyer: {e}")
        # Wrap coroutine for apscheduler
        def run_async_job():
            asyncio.run(_job())
        run_date = when
        if freq == "daily":
            scheduler.add_job(run_async_job, "cron", hour=run_date.hour, minute=run_date.minute, id=job_id)
        else:
            scheduler.add_job(run_async_job, "date", run_date=run_date, id=job_id)

    @app.on_message(filters.command("scheduleflyer"))
    async def schedule_flyer(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can schedule flyers.")
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <group> [daily|once]")
        name, hhmm, group = args[1], args[2], args[3]
        freq = "daily"
        if len(args) > 4 and args[4].lower() in ("daily", "once"):
            freq = args[4].lower()
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        group_id = get_group_id(group)
        if not group_id:
            return await message.reply("❌ Invalid group/alias.")
        # Parse time as today (use scheduler tz!)
        tz = scheduler.timezone
        now = datetime.now(tz)
        hour, minute = map(int, hhmm.split(":"))
        post_time = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if post_time < now:
            post_time += timedelta(days=1)
        job_id = f"flyer_{name}_{group_id}_{post_time.timestamp()}"
        schedule_flyer_post(group_id, name, post_time, freq, job_id=job_id)
        await message.reply(f"✅ Scheduled flyer '{name}' to {group} at {hhmm} ({freq}).\nTime zone: {tz}")

    @app.on_message(filters.command("scheduletext"))
    async def schedule_text(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can schedule flyers.")
        args = message.text.split(maxsplit=4)
        if len(args) < 5:
            return await message.reply("❌ Usage: /scheduletext <HH:MM> <group> <text> [daily|once]")
        hhmm, group, text = args[1], args[2], args[3]
        freq = "daily" if len(args) > 4 and args[4].lower() == "daily" else "once"
        group_id = get_group_id(group)
        if not group_id:
            return await message.reply("❌ Invalid group/alias.")
        name = "text_" + str(uuid.uuid4())[:8]
        flyers.insert_one({"name": name, "caption": text, "type": "text", "owner": message.from_user.id})
        tz = scheduler.timezone
        now = datetime.now(tz)
        hour, minute = map(int, hhmm.split(":"))
        post_time = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if post_time < now:
            post_time += timedelta(days=1)
        job_id = f"flyer_{name}_{group_id}_{post_time.timestamp()}"
        schedule_flyer_post(group_id, name, post_time, freq, job_id=job_id)
        await message.reply(f"✅ Scheduled text flyer to {group} at {hhmm} ({freq}). [job_id: {job_id}]")

    @app.on_message(filters.command("listscheduled"))
    async def list_scheduled(client, message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply("No flyers scheduled.")
        msg = "Scheduled Flyers:\n"
        for job in jobs:
            jid = job.id
            if jid.startswith("flyer_"):
                parts = jid.split("_")
                flyer_name, group, timestamp = parts[1], parts[2], parts[3]
                flyer = flyers.find_one({"name": flyer_name})
                flyer_type = flyer["type"] if flyer else "?"
                tstr = str(datetime.fromtimestamp(float(timestamp)))
                msg += f"- <b>{flyer_name}</b> ({flyer_type}) to <code>{group}</code> at {tstr} [job_id: <code>{jid}</code>]\n"
        await message.reply(msg)

    @app.on_message(filters.command("cancelflyer"))
    async def cancel_flyer(client, message):
        if not await ensure_admin(message):
            return await message.reply("❌ Only admins can cancel flyers.")
        args = message.text.split()
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = args[1]
        try:
            scheduler.remove_job(job_id)
            await message.reply("✅ Flyer canceled.")
        except Exception as e:
            await message.reply(f"❌ Failed to cancel: {e}")
