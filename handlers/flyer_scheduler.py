import os
import logging
import pytz
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# ---- MongoDB ----
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo["flyers"]

GROUP_ALIASES = {
    "MODELS_CHAT": -1002884098395,
    "SUCCUBUS_SANCTUARY": -1002823762054,
    "TEST_GROUP": -1002813378700,
}
SUPER_ADMIN_ID = 6964994611

async def is_admin(client: Client, chat_id: int, user_id: int):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def register(app: Client, scheduler):
    logger.info("📢 flyer_scheduler.register() called")

    # --- Schedule flyer by name ---
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return
        if len(message.command) < 4:
            await message.reply("❌ Usage: /scheduleflyer <name> <HH:MM> <chat>")
            return
        name = message.command[1]
        time_str = message.command[2]
        group_alias = message.command[3].upper()
        group_id = GROUP_ALIASES.get(group_alias)
        if not group_id:
            await message.reply(f"❌ Unknown group alias. Valid: {', '.join(GROUP_ALIASES)}")
            return
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            await message.reply("❌ Flyer not found!")
            return

        tz = pytz.timezone(os.environ.get("SCHEDULER_TZ", "America/Los_Angeles"))
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(tz)
        run_time = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if run_time < now:
            run_time += timedelta(days=1)
        job_id = f"flyer_{name}_{group_id}_{int(run_time.timestamp())}"

        async def flyer_job():
            try:
                if flyer["type"] == "photo":
                    await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
                else:
                    await app.send_message(group_id, flyer.get("text", flyer.get("caption", "")))
            except Exception as e:
                logger.exception(f"Failed scheduled flyer post: {e}")

        scheduler.add_job(lambda: app.loop.create_task(flyer_job()), 'date', run_date=run_time, id=job_id)
        await message.reply(f"✅ Scheduled flyer '{name}' for {group_alias} at {run_time.strftime('%Y-%m-%d %H:%M %Z')}\nJob ID: <code>{job_id}</code>")

    # --- List scheduled jobs ---
    @app.on_message(filters.command("listscheduled") & filters.group)
    async def listscheduled_handler(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            await message.reply("No flyers scheduled.")
            return
        lines = []
        for job in jobs:
            lines.append(f"- {job.id}: {job.next_run_time}")
        await message.reply("📅 <b>Scheduled Flyers</b>:\n" + "\n".join(lines))

    # --- Cancel scheduled job ---
    @app.on_message(filters.command("cancelflyer") & filters.group)
    async def cancelflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return
        if len(message.command) < 2:
            await message.reply("❌ Usage: /cancelflyer <job_id>")
            return
        job_id = message.command[1]
        job = scheduler.get_job(job_id)
        if job:
            scheduler.remove_job(job_id)
            await message.reply(f"✅ Canceled job {job_id}")
        else:
            await message.reply("❌ No job found with that ID.")

    # --- Schedule a text post ---
    @app.on_message(filters.command("scheduletext") & filters.group)
    async def scheduletext_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return
        if len(message.command) < 4:
            await message.reply("❌ Usage: /scheduletext <HH:MM> <chat> <text>")
            return
        time_str = message.command[1]
        group_alias = message.command[2].upper()
        text = " ".join(message.command[3:])
        group_id = GROUP_ALIASES.get(group_alias)
        if not group_id:
            await message.reply(f"❌ Unknown group alias. Valid: {', '.join(GROUP_ALIASES)}")
            return

        tz = pytz.timezone(os.environ.get("SCHEDULER_TZ", "America/Los_Angeles"))
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(tz)
        run_time = tz.localize(datetime(now.year, now.month, now.day, hour, minute))
        if run_time < now:
            run_time += timedelta(days=1)
        job_id = f"text_{group_id}_{int(run_time.timestamp())}"

        async def text_job():
            try:
                await app.send_message(group_id, text)
            except Exception as e:
                logger.exception(f"Failed scheduled text post: {e}")

        scheduler.add_job(lambda: app.loop.create_task(text_job()), 'date', run_date=run_time, id=job_id)
        await message.reply(f"✅ Scheduled text post for {group_alias} at {run_time.strftime('%Y-%m-%d %H:%M %Z')}\nJob ID: <code>{job_id}</code>")
