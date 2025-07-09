import os
import logging
import pkgutil
import importlib
from pyrogram import Client
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# Logging
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Env
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")
SCHED_TZ = timezone("America/Los_Angeles")

# Init bot
app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Scheduler
scheduler = BackgroundScheduler(timezone=SCHED_TZ)
scheduler.start()
logger.info("⏰ Scheduler started.")

# Register all handlers
def register_all_handlers(app):
    for _, module_name, _ in pkgutil.iter_modules(["handlers"]):
        module = importlib.import_module(f"handlers.{module_name}")
        if hasattr(module, "register"):
            module.register(app, scheduler)
        logger.info(f"✅ Registered handler: handlers.{module_name}")
    logger.info("✅ All handlers registered. Starting bot...")

register_all_handlers(app)
app.run()
