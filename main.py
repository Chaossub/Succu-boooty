import os
import logging
from dotenv import load_dotenv

print("MAIN.PY BOOTSTRAP BEGIN")
logging.basicConfig(level=logging.INFO)
load_dotenv()
print("Loaded environment.")

from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
scheduler.start()
logging.info("Scheduler started.")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

print("Registering handlers...")
try:
    from handlers import (
        welcome,
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer,
        flyer_scheduler,
    )
    logging.info("Imported all handler modules.")
    welcome.register(app)
    logging.info("Registered welcome.")
    help_cmd.register(app)
    logging.info("Registered help_cmd.")
    moderation.register(app)
    logging.info("Registered moderation.")
    federation.register(app)
    logging.info("Registered federation.")
    summon.register(app)
    logging.info("Registered summon.")
    xp.register(app)
    logging.info("Registered xp.")
    fun.register(app)
    logging.info("Registered fun.")
    flyer.register(app)
    logging.info("Registered flyer.")

    # Get the scheduled queue worker from flyer_scheduler.register
    scheduled_queue_worker = flyer_scheduler.register(app, scheduler)
    logging.info("Registered flyer_scheduler.")
except Exception as e:
    logging.error(f"🔥 Exception during handler registration: {e}")
    import traceback; traceback.print_exc()
    raise

print("✅ SuccuBot is running...")

import asyncio

if __name__ == "__main__":
    app.start()
    # Start the flyer scheduler background worker
    app.loop.create_task(scheduled_queue_worker())
    print("✅ SuccuBot is running (async worker started)...")
    app.idle()
