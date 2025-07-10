import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Scheduler for scheduled posts
scheduler = BackgroundScheduler()

# Import and register handlers
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

print("✅ SuccuBot is running...")
register_all_handlers(app)
app.run()
