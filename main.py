import os
import logging
from dotenv import load_dotenv

# --- Load environment ---
load_dotenv()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("root")

# --- Scheduler ---
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
scheduler.start()
logger.info("Scheduler started.")

# --- Telegram Bot ---
from pyrogram import Client
from pyrogram.enums import ParseMode

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

logger.info("Registering handlers...")

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
        flyer_scheduler,
    )
    welcome.register(app)
    logger.info("Registered welcome.")
    help_cmd.register(app)
    logger.info("Registered help_cmd.")
    moderation.register(app)
    logger.info("Registered moderation.")
    federation.register(app)
    logger.info("Registered federation.")
    summon.register(app)
    logger.info("Registered summon.")
    xp.register(app)
    logger.info("Registered xp.")
    fun.register(app)
    logger.info("Registered fun.")
    flyer.register(app)
    logger.info("Registered flyer.")
    flyer_scheduler.register(app, scheduler)
    logger.info("Registered flyer_scheduler.")
except Exception as e:
    logger.error(f"🔥 Exception during handler registration: {e}")
    import traceback; traceback.print_exc()
    raise

logger.info("✅ SuccuBot is running...")

try:
    app.run()
except Exception as e:
    logger.error(f"🔥 Exception during app.run(): {e}")
    import traceback; traceback.print_exc()
    raise
