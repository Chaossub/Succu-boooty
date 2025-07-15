import os
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
load_dotenv()

from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")

scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

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
    )
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)
except Exception as e:
    logging.exception(f"🔥 Handler registration failed: {e}")

logging.info("✅ SuccuBot is running...")
try:
    app.run()
except Exception as e:
    logging.exception(f"🔥 Exception in app.run(): {e}")
