import os
import logging
from pyrogram import filters
from pyrogram.types import Message, InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Mongo Setup ---
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo["flyers"]
sched_col = mongo["flyer_schedules"]

# --- Group Aliases (convert all to int) ---
ALIASES = {
    "MODELS_CHAT": int(os.environ["MODELS_CHAT"]),
    "SUCCUBUS_SANCTUARY": int(os.environ["SUCCUBUS_SANCTUARY"]),
    "TEST_GROUP": int(os.environ["TEST_GROUP"]),
}
SUPER_ADMIN_ID = 6964994611

def resolve_chat_id(target):
    if isinstance(target, str):
        if target.upper() in ALIASES:
            return ALIASES[target.upper()]
        if target.startswith('-100') and target[1:].isdigit():
            return int(target)
        try:
            return int(target)
        except:
            pass
    elif isinstance(target, int):
        return target
    raise ValueError("Invalid group/alias.")

# --- Helpers ---
def is_admin_or_owner(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

# --- Main Register Function ---
def register(app, scheduler: BackgroundScheduler):
    logger.info("📢 flyer.register() called")

    def admin_only(fn):
        async def wrapper(client, message: Message):
            chat_id = message.chat.id
            user_id = message.from_user.id
            if chat_id < 0 and not await app.loop.run_in_executor(None, is_admin_or_owner, app, chat_id, user_id):
                return await message.reply("❌ Only admins can add flyers.")
            return await fn(client, message)
        return wrapper

    @app.on_message(filters.command("addflyer") & filters.group)
    @admin_only
    async def add_flyer(client, message: Message):
        args = message.text.split(None, 2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")
        name, caption = args[1], args[2]

        # If photo attached (not as a reply)
        if message.photo:
            file_id = message.photo.file_id
            flyers_col.update_one(
                {"name": name},
                {"$set": {"name": name, "caption": caption, "file_id": file_id, "type": "photo"}},
                upsert=True
            )
            return await message.reply(f"✅ Photo flyer '{name}' added.")
        else:
            flyers_col.update_one(
                {"name": name},
                {"$set": {"name": name, "caption": caption, "type": "text"}},
                upsert=True
            )
            return await message.reply(f"✅ Text flyer '{name}' added.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = args[1]
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer.get("type") == "photo":
            await message.reply_photo(flyer["file_id"], caption=flyer["caption"])
        else:
            await message.reply(flyer["caption"])

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = [f['name'] for f in flyers_col.find({})]
        if not flyers:
            return await message.reply("No flyers found.")
        await message.reply("Flyers:\n" + "\n".join(f"- {x}" for x in flyers))

    @app.on_message(filters.command("deleteflyer") & filters.group)
    @admin_only
    async def delete_flyer(client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1]
        res = flyers_col.delete_one({"name": name})
        if res.deleted_count:
            await message.reply(f"✅ Deleted flyer '{name}'.")
        else:
            await message.reply("❌ Flyer not found.")

    # --- SCHEDULING ---
    def flyer_job(flyer_name, group, once, when=None):
        async def _job():
            group_id = resolve_chat_id(group)
            logger.info(f"Trying to post flyer '{flyer_name}' to {group_id} (type: {type(group_id)})")
            flyer = flyers_col.find_one({"name": flyer_name})
            if not flyer:
                logger.error("Scheduled flyer not found.")
                return
            try:
                if flyer.get("type") == "photo":
                    await app.send_photo(group_id, flyer["file_id"], caption=flyer["caption"])
                else:
                    await app.send_message(group_id, flyer["caption"])
            except Exception as e:
                logger.error(f"Failed to post flyer: {e}")
            if once:
                sched_col.delete_one({"name": flyer_name, "group": group})
        return _job

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    @admin_only
    async def schedule_flyer(client, message: Message):
        try:
            _, flyer_name, group_alias, time_str, *args = message.text.split(None, 4)
            freq = args[0] if args else "once"
        except Exception:
            return await message.reply("❌ Usage: /scheduleflyer <name> <group> <HH:MM> [once|daily]")
        flyer = flyers_col.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        group_id = resolve_chat_id(group_alias)
        when = datetime.now(pytz.timezone(os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")))
        hour, minute = map(int, time_str.split(":"))
        fire_at = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if fire_at < when:
            fire_at += timedelta(days=1)
        job_id = f"flyer_{flyer_name}_{group_id}_{fire_at.timestamp()}"
        if freq == "daily":
            scheduler.add_job(flyer_job(flyer_name, group_alias, once=False), "cron", hour=hour, minute=minute, id=job_id)
        else:
            scheduler.add_job(flyer_job(flyer_name, group_alias, once=True), "date", run_date=fire_at, id=job_id)
        sched_col.insert_one({"name": flyer_name, "group": group_alias, "time": time_str, "freq": freq, "job_id": job_id})
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' to {group_alias} at {time_str} ({freq}).")

    @app.on_message(filters.command("listscheduled") & filters.group)
    async def list_scheduled(client, message: Message):
        jobs = list(sched_col.find({}))
        if not jobs:
            return await message.reply("No flyers scheduled.")
        txt = "Scheduled Flyers:\n" + "\n".join(
            f"- {j['name']} to {j['group']} at {j['time']} ({j['freq']})" for j in jobs
        )
        await message.reply(txt)

    @app.on_message(filters.command("cancelflyer") & filters.group)
    @admin_only
    async def cancel_flyer(client, message: Message):
        args = message.text.split(None, 1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = args[1]
        scheduler.remove_job(job_id)
        sched_col.delete_one({"job_id": job_id})
        await message.reply(f"✅ Cancelled scheduled flyer (job_id: {job_id})")

