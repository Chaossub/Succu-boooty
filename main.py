import os
import logging
import importlib
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Load .env ────────────────────────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Mongo vars used by flyer
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME")

# ─── Setup Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Pyrogram App ─────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Scheduler ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Register Handlers ────────────────────────────────────────────────────────
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
    flyer.register(app, scheduler)  # Pass scheduler to flyer

    logger.info("✅ All handlers registered.")

# ─── Main Run ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    register_all_handlers(app)
    logger.info("✅ SuccuBot is running...")
    app.run()
