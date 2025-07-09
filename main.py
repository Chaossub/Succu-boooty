import os
import logging
import importlib
import pkgutil

from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Initialize scheduler
scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "UTC"))
scheduler.start()
logging.info("⏰ Scheduler started.")

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
    flyer.register(app)  # Do NOT pass scheduler; it's internal

    logging.info("✅ All handlers registered.")

# Run bot
if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        level=logging.INFO,
    )
    register_all_handlers(app)
    logging.info("✅ SuccuBot is running...")
    app.run()
