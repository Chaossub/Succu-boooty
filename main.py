# main.py (fully corrected)
import os
import logging
import pkgutil
import importlib
import inspect
from pymongo import MongoClient
from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "UTC")
RAW_WHITE = os.environ.get("FLYER_WHITELIST", "")
WHITELIST = [int(x) for x in RAW_WHITE.split(",") if x.strip()]

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

scheduler = AsyncIOScheduler(timezone=SCHED_TZ)

handlers_dir = os.path.join(os.path.dirname(__file__), "handlers")

for _, module_name, _ in pkgutil.iter_modules([handlers_dir]):
    module = importlib.import_module(f"handlers.{module_name}")
    if not hasattr(module, "register"):
        continue

    sig = inspect.signature(module.register)
    params = sig.parameters
    kwargs = {}

    for name in ("app", "bot", "client"):
        if name in params:
            kwargs[name] = app
            break

    if "scheduler" in params:
        kwargs["scheduler"] = scheduler
    if "db" in params:
        kwargs["db"] = db
    if "whitelist" in params:
        kwargs["whitelist"] = WHITELIST

    module.register(**kwargs)
    logger.info(f"Registered handler: handlers.{module_name}.register")

if __name__ == "__main__":
    scheduler.start()  # Explicitly start scheduler here
    logger.info("⏰ Scheduler started.")
    logger.info("📥 All handlers registered. Starting bot…")
    app.run()
