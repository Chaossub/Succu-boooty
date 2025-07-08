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
API_ID     = os.environ.get("API_ID")
API_HASH   = os.environ.get("API_HASH")
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
MONGO_URI  = os.environ.get("MONGO_URI")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")
SCHEDULER_TZ  = os.environ.get("SCHEDULER_TZ", "UTC")
FLYER_WHITELIST_RAW = os.environ.get("FLYER_WHITELIST", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing one of: API_ID, API_HASH, BOT_TOKEN")
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN in env")

if not MONGO_URI or not MONGO_DB_NAME:
    logger.error(f"MONGO_URI set? {bool(MONGO_URI)}, MONGO_DB_NAME set? {bool(MONGO_DB_NAME)}")
    raise RuntimeError("Please set MONGO_URI and MONGO_DB_NAME (or MONGO_DBNAME) in env")

# ─── Initialize MongoDB ─────────────────────────────────────────────────────
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]

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

# ─── Import & register all handlers ─────────────────────────────────────────

# Core / help
from handlers.help import register as register_help
register_help(bot=app)

# Summon commands
from handlers.summon import register as register_summon
register_summon(bot=app, db=db)

# Fun commands (bite, spank, tease…)
from handlers.fun import register as register_fun
register_fun(bot=app, db=db)

# XP commands (naughty, leaderboard…)
from handlers.xp import register as register_xp
register_xp(bot=app, db=db)

# Moderation (warn, mute, kick, ban…)
from handlers.mod import register as register_mod
register_mod(bot=app, db=db)

# Federation (createfed, fedban…)
from handlers.fed import register as register_fed
register_fed(bot=app, db=db)

# Flyer (scheduleflyer, addflyer…)
from handlers.flyer import register as register_flyer
whitelist = [int(cid.strip()) for cid in FLYER_WHITELIST_RAW.split(",") if cid.strip()]
register_flyer(bot=app, scheduler=scheduler, db=db, whitelist=whitelist)

# ─── Start ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("📥 Registering handlers…")
    logger.info("✅ Bot is starting up…")
    app.run()
