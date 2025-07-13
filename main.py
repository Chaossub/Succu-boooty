import os
import logging
from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
import uvicorn
from pyrogram import Client
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

# ─── FastAPI App ───────────────────────────────────────────────────────────────
api = FastAPI()

@api.get("/")
async def root():
    return {"status": "ok"}

# ─── Pyrogram Bot ───────────────────────────────────────────────────────────────
bot = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Scheduler ─────────────────────────────────────────────────────────────────
sched_tz  = timezone(TZ)
scheduler = AsyncIOScheduler(timezone=sched_tz)

# ─── Register Handlers ─────────────────────────────────────────────────────────
from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer

welcome.register(bot)
help_cmd.register(bot)
moderation.register(bot)
federation.register(bot)
summon.register(bot)
xp.register(bot)
fun.register(bot)
# Flyer needs the scheduler reference
flyer.register(bot, scheduler)

# ─── Startup/Shutdown Events ───────────────────────────────────────────────────
@api.on_event("startup")
async def on_startup():
    await bot.start()
    scheduler.start()
    logger.info("✅ Bot and AsyncIO Scheduler started")

@api.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown(wait=False)
    await bot.stop()
    logger.info("🛑 Bot and Scheduler stopped")

# ─── Run Uvicorn ASGI Server ──────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:api",   # module:app
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
