import os
import logging
import asyncio

from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pyrogram import Client
from pyrogram.enums import ParseMode
import uvicorn

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
app = FastAPI()

@app.get("/")
async def health_check():
    return {"status": "ok"}

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
# Flyer needs the scheduler reference
flyer.register(bot, scheduler)

# ─── Application Entry Point ──────────────────────────────────────────────────
async def main():
    # 1) start the scheduler
    scheduler.start()
    logger.info("✅ AsyncIO Scheduler started")

    # 2) start the bot
    await bot.start()
    logger.info("🤖 Pyrogram bot started")

    # 3) run the FastAPI+uvicorn server (blocks here until termination)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()

    # 4) on shutdown, clean up
    await bot.stop()
    logger.info("🛑 Pyrogram bot stopped")
    scheduler.shutdown(wait=False)
    logger.info("🛑 Scheduler shut down")

if __name__ == "__main__":
    asyncio.run(main())
