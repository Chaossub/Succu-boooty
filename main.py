import os
import logging
import pkgutil
import importlib
import inspect

from pymongo import MongoClient
from pyrogram import Client
from apscheduler.schedulers.background import BackgroundScheduler

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Environment ────────────────────────────────────────────────────────────
API_ID        = os.getenv("API_ID")
API_HASH      = os.getenv("API_HASH")
BOT_TOKEN     = os.getenv("BOT_TOKEN")
MONGO_URI     = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")
SCHEDULER_TZ  = os.getenv("SCHEDULER_TZ", "UTC")
raw_whitelist = os.getenv("FLYER_WHITELIST", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN in env")

if not MONGO_URI or not MONGO_DB_NAME:
    raise RuntimeError("Please set MONGO_URI and MONGO_DB_NAME in env")

# ─── MongoDB ────────────────────────────────────────────────────────────────
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]

# ─── Telegram Bot ───────────────────────────────────────────────────────────
app = Client(
    "bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ─── Scheduler ──────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()

# ─── Dynamically import all handlers ────────────────────────────────────────
whitelist = [int(x) for x in raw_whitelist.split(",") if x.strip()]

handlers_pkg = os.path.join(os.path.dirname(__file__), "handlers")
for finder, name, ispkg in pkgutil.iter_modules([handlers_pkg]):
    module = importlib.import_module(f"handlers.{name}")
    if hasattr(module, "register"):
        sig = inspect.signature(module.register)
        params = sig.parameters
        kwargs = {}
        if "app" in params or "bot" in params:
            # whichever your handler expects, pass the same `app`
            key = "app" if "app" in params else "bot"
            kwargs[key] = app
        if "scheduler" in params:
            kwargs["scheduler"] = scheduler
        if "db" in params:
            kwargs["db"] = db
        if "whitelist" in params:
            kwargs["whitelist"] = whitelist

        module.register(**kwargs)
        logger.info(f"Registered handler: handlers.{name}.register")

# ─── Start ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("📥 Handlers all registered, starting bot…")
    app.run()
