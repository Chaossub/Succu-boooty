import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(asctime)s - %(message)s'
)

logging.info("Loading environment variables...")
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

if not API_ID or not API_HASH or not BOT_TOKEN or not MONGO_URI:
    logging.error("One or more required environment variables are missing!")
    exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    logging.error("API_ID must be an integer!")
    exit(1)

logging.info("Starting SuccuBot client...")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import handlers here
from handlers import (
    moderation,
    federation,
    xp,
    warnings,
    summon,
    fun,
    flyer,
    welcome,
    help_cmd
)

logging.info("Registering handlers...")

try:
    moderation.register(app)
    federation.register(app)
    xp.register(app)
    warnings.register(app)
    summon.register(app)
    fun.register(app)
    flyer.register(app)
    welcome.register(app)
    help_cmd.register(app)
except Exception as e:
    logging.error(f"Error registering handlers: {e}", exc_info=True)
    exit(1)

logging.info("✅ SuccuBot is running...")

app.run()
