import os
import logging

from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, idle
from pyrogram.enums import ParseMode

# ─── Environment & Logging ─────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TZ        = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")

# ─── Pyrogram Bot ───────────────────────────────────────────────────────────────
bot = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── AsyncIO Scheduler ─────────────────────────────────────────────────────────
sched_tz   = timezone(TZ)
scheduler  = AsyncIOScheduler(timezone=sched_tz)

# ─── Register Handlers ─────────────────────────────────────────────────────────
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

welcome.register(bot)
help_cmd.register(bot)
moderation.register(bot)
federation.register(bot)
summon.register(bot)
xp.register(bot)
fun.register(bot)
# flyer needs the scheduler reference
flyer.register(bot, scheduler)

# ─── Bot Startup ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) Start the scheduler
    scheduler.start()
    logger.info("✅ AsyncIO Scheduler started")

    # 2) Start the bot
    bot.start()
    logger.info("🤖 Pyrogram bot started")

    # 3) Block here until Ctrl+C or SIGTERM
    idle()

    # (if idle ever returns, clean up)
    bot.stop()
    scheduler.shutdown(wait=False)
    logger.info("🛑 Clean shutdown complete")
