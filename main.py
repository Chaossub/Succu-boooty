import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME")  # Correct variable name for Railway

if not isinstance(MONGO_DB, str) or not MONGO_DB:
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DBNAME environment variable.")

# Scheduler
scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
scheduler.start()
logging.info("⏰ Scheduler started.")

# Logging
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

def register_all_handlers(app):
    from handlers import (
        help_cmd,
        welcome,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer
    )

    help_cmd.register(app)
    welcome.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

register_all_handlers(app)

print("✅ SuccuBot is running...")
app.run()

