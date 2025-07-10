import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env vars
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUCCUBUS_SANCTUARY = int(os.getenv("SUCCUBUS_SANCTUARY", "0"))
MODELS_CHAT = int(os.getenv("MODELS_CHAT", "0"))
TEST_GROUP = int(os.getenv("TEST_GROUP", "0"))

# Scheduler setup
scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "UTC"))
scheduler.start()

# Initialize bot
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import and register all handlers
from handlers import (
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    welcome,
    flyer,
)

def register_all_handlers(app):
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    welcome.register(app)
    flyer.register(app, scheduler)

register_all_handlers(app)

print("✅ SuccuBot is running...")
app.run()

