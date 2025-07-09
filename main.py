import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Start scheduler
scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
scheduler.start()
logging.info("⏰ Scheduler started.")

# Import and register handlers
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
flyer.register(app, scheduler)  # Scheduler is passed here

print("✅ SuccuBot is running...")
app.run()
