import os
import logging

from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pyrogram import Client
from pyrogram.enums import ParseMode

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TZ        = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", 8000))

# FastAPI app (will keep container alive)
app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "ok"}

# Pyrogram client
bot = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# AsyncIO scheduler
sched_tz   = timezone(TZ)
scheduler  = AsyncIOScheduler(timezone=sched_tz)

# Register your handlers
from handlers import (
    welcome, help_cmd, moderation, federation,
    summon, xp, fun, flyer
)
welcome.register(bot)
help_cmd.register(bot)
moderation.register(bot)
federation.register(bot)
summon.register(bot)
xp.register(bot)
fun.register(bot)
flyer.register(bot, scheduler)

# FastAPI startup/shutdown events
@app.on_event("startup")
async def on_startup():
    logger.info("🔌 Starting bot and scheduler...")
    await bot.start()
    scheduler.start()
    logger.info("✅ Bot and scheduler running.")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🛑 Shutting down scheduler and bot...")
    scheduler.shutdown(wait=False)
    await bot.stop()
    logger.info("✅ Clean shutdown complete.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",       # module:app
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        lifespan="on"     # ensure startup/shutdown events fire
    )
