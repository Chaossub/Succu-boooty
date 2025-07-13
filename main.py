# main.py
import os
import logging
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ─── Load env & logging ─────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Scheduler ──────────────────────────────────────────────────────────────
sched_tz   = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
scheduler  = BackgroundScheduler(timezone=timezone(sched_tz))
scheduler.start()
logger.info("🔌 Scheduler started")

# ─── Bot client ─────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
)
logger.info("📢 Registering handlers…")
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
flyer.register(app, scheduler)

logger.info("✅ SuccuBot is running…")
app.run()
