import os
import logging
from datetime import datetime, timedelta
from pyrogram import filters
from pymongo import MongoClient
import asyncio

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers
scheduled = db.scheduled_flyers

ADMIN_IDS = [6964994611]

ALIASES = {
    "MODELS_CHAT": int(os.environ["MODELS_CHAT"]),
    "SUCCUBUS_SANCTUARY": int(os.environ["SUCCUBUS_SANCTUARY"]),
    "TEST_GROUP": int(os.environ["TEST_GROUP"]),
}

def admin_filter(_, __, m):
    return m.from_user and m.from_user.id in ADMIN_IDS

# --- NEW: This global queue will be checked by an async worker in Pyrogram loop
SCHEDULED_QUEUE = []

def register(app, scheduler):
    async def flyer_job(group_id, flyer_name):
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            logging.error(f"Flyer '{flyer_name}' not found!")
            return
        try:
            if flyer.get("file_id"):
                await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
            else:
                await app.send_message(group_id, flyer.get("caption", ""))
            logging.info(f"✅ Scheduled flyer posted: {flyer_name} -> {group_id}")
        except Exception as e:
            logging.error(f"Failed scheduled flyer post: {e}")

    def threadsafe_enqueue(group_id, flyer_name):
        SCHEDULED_QUEUE.append((group_id, flyer_name))

    @app.on_message(filters.command("scheduleflyer") & filters.create(admin_filter))
    async def scheduleflyer_handler(client, message):
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <group_alias> <HH:MM> [once|daily|weekly]")
        flyer_name, group_alias, time_str = args[1:4]
        freq = args[4] if len(args) > 4 else "once"
        group_id = ALIASES.get(group_alias)
        if not group_id:
            return await message.reply("❌ Invalid group/alias.")
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        job_id = f"flyer_{flyer_name}_{group_id}_{int(run_time.timestamp())}"
        if freq == "once":
            scheduler.add_job(
                lambda: threadsafe_enqueue(group_id, flyer_name),
                "date", run_date=run_time, id=job_id
            )
        elif freq == "daily":
            scheduler.add_job(
                lambda: threadsafe_enqueue(group_id, flyer_name),
                "cron", hour=hour, minute=minute, id=job_id
            )
        elif freq == "weekly":
            scheduler.add_job(
                lambda: threadsafe_enqueue(group_id, flyer_name),
                "cron", day_of_week="mon", hour=hour, minute=minute, id=job_id
            )
        else:
            return await message.reply("❌ Invalid freq. Use once/daily/weekly")
        scheduled.insert_one({"job_id": job_id, "flyer_name": flyer_name, "group_id": group_id, "time": time_str, "freq": freq})
        await message.reply(
            f"✅ Scheduled flyer '<b>{flyer_name}</b>' to <b>{group_alias}</b> at <b>{time_str}</b> ({freq}).\n"
            f"Job ID: <code>{job_id}</code>"
        )

    @app.on_message(filters.command("listscheduled") & filters.create(admin_filter))
    async def list_scheduled(client, message):
        jobs = list(scheduled.find({}))
        if not jobs:
            await message.reply("No flyers scheduled.")
        else:
            lines = [
                f"• <b>{j['flyer_name']}</b> to {j['group_id']} at {j['time']} ({j['freq']}) [job_id: <code>{j['job_id']}</code>]"
                for j in jobs
            ]
            await message.reply("Scheduled Flyers:\n" + "\n".join(lines))

    @app.on_message(filters.command("cancelflyer") & filters.create(admin_filter))
    async def cancelflyer(client, message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /cancelflyer <job_id>")
        job_id = args[1].strip()
        try:
            scheduler.remove_job(job_id)
            scheduled.delete_one({"job_id": job_id})
            await message.reply("✅ Scheduled flyer canceled.")
        except Exception as e:
            await message.reply(f"❌ Could not cancel: {e}")

    # NEW: Periodically check and run scheduled jobs in Pyrogram event loop
    async def scheduled_queue_worker():
        while True:
            if SCHEDULED_QUEUE:
                group_id, flyer_name = SCHEDULED_QUEUE.pop(0)
                await flyer_job(group_id, flyer_name)
            await asyncio.sleep(3)  # Check every 3 seconds

    # Register this background worker after app starts
    @app.on_start
    async def start_worker(_: "Client"):
        app.loop.create_task(scheduled_queue_worker())
