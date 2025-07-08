import os
import logging
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
# Telegram
API_ID   = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing one of: API_ID, API_HASH, BOT_TOKEN")
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN in env")

# Mongo
MONGO_URI = os.environ.get("MONGO_URI")
# support either MONGO_DB_NAME or MONGO_DBNAME
MONGO_DB_NAME = (
    os.environ.get("MONGO_DB_NAME")
    or os.environ.get("MONGO_DBNAME")
)

if not MONGO_URI or not MONGO_DB_NAME:
    logger.error(
        f"MONGO_URI={bool(MONGO_URI)}, "
        f"MONGO_DB_NAME={bool(MONGO_DB_NAME)}"
    )
    raise RuntimeError("Please set MONGO_URI and MONGO_DB_NAME (or MONGO_DBNAME) in env")

# Scheduler timezone (optional)
SCHEDULER_TZ = os.environ.get("SCHEDULER_TZ", "UTC")

# ─── Initialize Mongo ────────────────────────────────────────────────────────
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]  # explicit database selection

# ─── Initialize Telegram Bot ────────────────────────────────────────────────
app = Client(
    "bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ─── Initialize Scheduler ───────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()

# ─── Register Handlers ──────────────────────────────────────────────────────
# flyer_handler.register(app, scheduler, db, whitelist=FLYER_WHITELIST)
# (import your flyer handler and pass along `db` and any other config)

from handlers.flyer import register as register_flyer

# If you have a FLYER_WHITELIST env var (comma-separated IDs):
raw = os.environ.get("FLYER_WHITELIST", "")
whitelist = [int(cid.strip()) for cid in raw.split(",") if cid.strip()]

register_flyer(
    bot=app,
    scheduler=scheduler,
    db=db,
    whitelist=whitelist,
)

# ─── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("📥 Registering handlers…")
    logger.info("✅ Bot is starting up…")
    app.run()
