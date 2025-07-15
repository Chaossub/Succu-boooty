import os
import logging
from pyrogram import filters
from pymongo import MongoClient
from datetime import datetime, timedelta

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

def register(app, scheduler):
    async def flyer_job(app, group_id, flyer_name):
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            logging.error(f"Flyer '{flyer_name}' not found!")
            return
        try:
            if flyer.get("file_id"):
                await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
            else:
                await app.send_message(group_id, flyer.get("caption", ""))
            logging.info(f"Posted scheduled flyer '{flyer_name}' to {group_id}")
        except Exception as e:
            logging.error(f"Failed scheduled flyer post: {e}")

    def restore_jobs():
        jobs = list(scheduled.find({}))
        for job in jobs:
            job_id = job["job_id"]
            flyer_name = job["flyer_name"]
            group_id = job["group_id"]
            freq = job.get("freq", "once")
            time_str = job.get("time")
            run_time_str = job.get("run_time")
            # Handle jobs with missing run_time
            if freq == "once" and not run_time_str:
                logging.warning(f"[restore_jobs] Skipping job {job_id} (missing run_time, probably old/corrupt)")
                continue
            # Calculate next run
            if freq == "once":
                run_time = datetime.strptime(run_time_str, "%Y-%m-%d %H:%M:%S")
                if run_time > datetime.now():
                    scheduler.add_job(
                        lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                        "date", run_date=run_time, id=job_id
                    )
            elif freq == "daily":
                hour, minute = map(int, time_str.split(":"))
                scheduler.add_job(
                    lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                    "cron", hour=hour, minute=minute, id=job_id
                )
            elif freq == "weekly":
                hour, minute = map(int, time_str.split(":"))
                scheduler.add_job(
                    lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                    "cron", day_of_week="mon", hour=hour, minute=minute, id=job_id
                )
        logging.info("Restored scheduled flyer jobs.")

    restore_jobs()

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
            scheduler.add_job(lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                              "date", run_date=run_time, id=job_id)
            run_time_str = run_time.strftime("%Y-%m-%d %H:%M:%S")
        elif freq == "daily":
            scheduler.add_job(lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                              "cron", hour=hour, minute=minute, id=job_id)
            run_time_str = None
        elif freq == "weekly":
            scheduler.add_job(lambda: app.loop.create_task(flyer_job(app, group_id, flyer_name)),
                              "cron", day_of_week="mon", hour=hour, minute=minute, id=job_id)
            run_time_str = None
        else:
            return await message.reply("❌ Invalid freq. Use once/daily/weekly")
        scheduled.insert_one({
            "job_id": job_id,
            "flyer_name": flyer_name,
            "group_id": group_id,
            "time": time_str,
            "freq": freq,
            "run_time": run_time_str
        })
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' to {group_alias} at {time_str} ({freq}).\nJob ID: <code>{job_id}</code>")

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
