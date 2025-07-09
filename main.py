import os
import asyncio
import logging
from fastapi import FastAPI
import uvicorn

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Load Environment Variables ─────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Mongo info passed to handlers
os.environ["MONGO_URI"] = os.getenv("MONGO_URI")
os.environ["MONGO_DBNAME"] = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")

# ─── Logging Setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── FastAPI Health Check Server ────────────────────────────────────────────
app_api = FastAPI()

@app_api.get("/")
async def root():
    return {"status": "ok"}

# ─── Initialize Bot & Scheduler ─────────────────────────────────────────────
bot = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode=ParseMode.HTML)
scheduler = AsyncIOScheduler()

# ─── Register Handlers ──────────────────────────────────────────────────────
def register_handlers():
    from handlers import (
        federation,
        flyer,
        fun,
        get_id,
        help_cmd,
        moderation,
        summon,
        test,
        warnings,
        welcome,
        xp
    )

    for module in [
        federation,
        flyer,
        fun,
        get_id,
        help_cmd,
        moderation,
        summon,
        test,
        warnings,
        welcome,
        xp
    ]:
        module.register(bot)
        logger.info(f"✅ Registered handler: {module.__name__}")

# ─── Async Main Startup ─────────────────────────────────────────────────────
async def main():
    logger.info("⏰ Scheduler started.")
    scheduler.start()

    register_handlers()
    logger.info("✅ Health server running. Starting bot...")

    await bot.start()
    await bot.idle()
    await bot.stop()

# ─── Launch ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # Run FastAPI in the background
        loop = asyncio.get_event_loop()
        loop.create_task(uvicorn.run(app_api, host="0.0.0.0", port=8000, log_level="info"))

        # Run bot main logic
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot interrupted and shutting down cleanly.")
