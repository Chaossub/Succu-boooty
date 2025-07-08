import os
import logging
import pkgutil
import importlib

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
# Any .py in handlers/ that defines `register(...)` will get hooked up.
whitelist = [int(x) for x in raw_whitelist.split(",") if x.strip()]

for finder, name, ispkg in pkgutil.iter_modules([os.path.join(os.path.dirname(__file__), "handlers")]):
    module = importlib.import_module(f"handlers.{name}")
    if hasattr(module, "register"):
        # signature: register(bot, scheduler=None, db=None, whitelist=None, …)
        kwargs = {"bot": app, "db": db, "scheduler": scheduler, "whitelist": whitelist}
        # prune any unused keys
        sig = importlib.signature(module.register)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        module.register(**filtered)
        logger.info(f"Registered handler: handlers.{name}.register")

# ─── Start ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("📥 Handlers all registered, starting bot…")
    app.run()
