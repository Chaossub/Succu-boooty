import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client, filters
from handlers.flyer import register as register_flyer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", "UTC")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set in env")

# Initialize Pyrogram client
app = Client(
    "succu_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Initialize APScheduler
scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()
logger.info("Scheduler started")

# Register commands/handlers from flyer.py
# NOTE: use positional args to match signature
register_flyer(app, scheduler)

# Start the bot
if __name__ == "__main__":
    app.run()
