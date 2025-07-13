import os
import logging
import threading

from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
import uvicorn

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
PORT      = int(os.getenv("PORT", 8000))

# ─── FastAPI “Keep-Alive” ───────────────────────────────────────────────────────
api = FastAPI()

@api.get("/")
async def root():
    return {"status": "ok"}

def run_api():
    uvicorn.run(api, host="0.0.0.0", port=PORT, log_level="info")

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
from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer

welcome.register(bot)
help_cmd.register(bot)
moderation.register(bot)
federation.register(bot)
summon.register(bot)
xp.register(bot)
fun.register(bot)
# flyer needs the scheduler reference
ayer.register(bot, scheduler)

# ─── Boot Sequence ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) Start FastAPI in non-daemon thread
    t = threading.Thread(target=run_api)
    t.start()
    logger.info(f"🚀 FastAPI server listening on port {PORT}")

    # 2) Start the AsyncIO scheduler
    scheduler.start()
    logger.info("✅ AsyncIO Scheduler started")

    # 3) Start the bot and block
    bot.start()
    logger.info("🤖 Pyrogram bot started")
    idle()
