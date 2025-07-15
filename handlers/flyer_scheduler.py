import os
import logging
from datetime import datetime, timedelta
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.triggers.date import DateTrigger
from pyrogram import filters
import pytz

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or "succubot"
TZ = pytz.timezone(os.environ.get("SCHEDULER_TZ", "America/Los_Angeles"))
OWNER_ID = int(os.environ.get("OWNER_ID") or 0)

mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyer_coll = mongo['flyers']

jobstores = {
    'default': MongoDBJobStore(
        client=MongoClient(MONGO_URI),
        database=MONGO_DB,
        collection='apscheduler_jobs'
    )
}
scheduler = BackgroundScheduler(jobstores=jobstores, timezone=TZ)
scheduler.start()

async def post_flyer(app, chat_id, flyer_data):
    try:
        await app.send_photo(
            chat_id=chat_id,
            photo=flyer_data['file_id'],
            caption=flyer_data.get('caption', '')
        )
    except Exception as e:
        print(f"[post_flyer] Failed: {e}")

def schedule_flyer_job(app, chat_id, flyer_data, run_datetime):
    job_id = f"flyer_{flyer_data['name']}_{chat_id}_{int(run_datetime.timestamp())}"
    scheduler.add_job(
        lambda: app.loop.create_task(post_flyer(app, chat_id, flyer_data)),
        trigger=DateTrigger(run_date=run_datetime),
        id=job_id,
        replace_existing=True,
        misfire_grace_time=600
    )

def is_admin(user_id, chat_id, client):
    member = client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")

def register(app):
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        if not is_admin(message.from_user.id, message.chat.id, client) and message.from_user.id != OWNER_ID:
            return await message.reply("❌ Admins only.")
        # Example: /scheduleflyer <name> <hour:minute> once
        try:
            _, flyer_name, time_str, *_ = message.text.split(maxsplit=3)
            flyer = flyer_coll.find_one({"chat_id": message.chat.id, "name": flyer_name})
            if not flyer:
                return await message.reply("❌ Flyer not found in this group.")
            run_time = datetime.strptime(time_str, "%H:%M").replace(
                year=datetime.now(TZ).year,
                month=datetime.now(TZ).month,
                day=datetime.now(TZ).day,
                tzinfo=TZ
            )
            if run_time < datetime.now(TZ):
                run_time += timedelta(days=1)
            schedule_flyer_job(app, message.chat.id, flyer, run_time)
            await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {run_time.strftime('%Y-%m-%d %H:%M')}.")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

# On startup: no manual restore needed! APScheduler + MongoDBJobStore does this for you.
