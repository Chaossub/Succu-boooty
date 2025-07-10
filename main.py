import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME")
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", "UTC")

# Validate required environment variables
if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in environment variables.")
if not MONGO_DB or not isinstance(MONGO_DB, str):
    raise ValueError("MONGO_DB must be a string. Please set the MONGO_DBNAME environment variable.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the bot
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Start the scheduler
scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()
logger.info("⏰ Scheduler started.")

# Register all handlers
def register_all_handlers(app):
    from handlers import (
        welcome,
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer
    )

    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

register_all_handlers(app)

# Run the bot
logger.info("✅ SuccuBot is running...")
app.run()
