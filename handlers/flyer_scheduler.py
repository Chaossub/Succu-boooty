import os
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")
OWNER_ID = int(os.environ.get("OWNER_ID", "6964994611"))  # Fallback to your Telegram ID

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers = db.flyers

GROUP_ALIASES = {
    k: int(v)
    for k, v in os.environ.items()
    if k.endswith("_ID")
    for v in [v] if v.lstrip('-').isdigit()
}

app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncIOScheduler(timezone=SCHED_TZ)

async def post_flyer_job(group_id, flyer_name):
    logger.info(f"Running post_flyer_job: group_id={group_id}, flyer_name={flyer_name}")
    flyer = flyers.find_one({"name": flyer_name})
    if not flyer:
        logger.error(f"Flyer '{flyer_name}' not found in DB.")
        return
    try:
        # Don't start/stop app here; it's already running
        if flyer.get("file_id"):
            await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await app.send_message(group_id, flyer.get("caption", ""))
        logger.info(f"Posted flyer '{flyer_name}' to {group_id}")
    except Exception as e:
        logger.error(f"Failed to post flyer: {e}")

async def scheduleflyer_handler(client, message):
    # Example: /scheduleflyer tipping 2025-07-18 21:30 once MODELS_CHAT
    if not (message.from_user and (message.from_user.is_admin or message.from_user.id == OWNER_ID)):
        return await message.reply("❌ Only admins can schedule flyers.")

    try:
        _, flyer_name, dt_str, repeat, group_alias = message.text.split(maxsplit=4)
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        group_id = GROUP_ALIASES.get(group_alias) or int(group_alias)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return await message.reply("❌ Usage: /scheduleflyer <name> <YYYY-MM-DD HH:MM> <once|daily|weekly> <group>")

    job_id = f"flyer_{flyer_name}_{group_id}_{dt.strftime('%Y%m%d%H%M%S')}"
    scheduler.add_job(post_flyer_job, "date", run_date=dt, args=[group_id, flyer_name], id=job_id)
    await message.reply(
        f"✅ Scheduled flyer '<b>{flyer_name}</b>' to post in <code>{group_alias}</code> at <b>{dt}</b>.\nJob ID: <code>{job_id}</code>",
        parse_mode="html"
    )
    logger.info(f"Scheduling flyer: {flyer_name} to {group_id} at {dt} | job_id={job_id}")

def register(app):
    from pyrogram import filters
    app.add_handler(filters.command("scheduleflyer"), scheduleflyer_handler)
    logger.info("Registered scheduleflyer handler.")

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started.")

if __name__ == "__main__":
    start_scheduler()
    app.run()
