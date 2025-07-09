import os
import logging
import pkgutil
import importlib
import inspect
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
SCHED_TZ = timezone("America/Los_Angeles")

# Init
app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = BackgroundScheduler(timezone=SCHED_TZ)
scheduler.start()
logger.info("⏰ Scheduler started.")

def register_all_handlers(app):
    for _, module_name, _ in pkgutil.iter_modules(["handlers"]):
        module = importlib.import_module(f"handlers.{module_name}")
        if hasattr(module, "register"):
            args = inspect.signature(module.register).parameters
            if len(args) == 2:
                module.register(app, scheduler)
            else:
                module.register(app)
            logger.info(f"✅ Registered handler: handlers.{module_name}")
    logger.info("✅ All handlers registered. Starting bot...")

register_all_handlers(app)
app.run()
