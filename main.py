import os
import asyncio
import logging

from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Logging setup
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bot client
app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode=ParseMode.HTML)
scheduler = AsyncIOScheduler()

# Import and register all handlers
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
    get_id,
    warnings,
    test
)

def register_handlers():
    for handler in [welcome, help_cmd, moderation, federation, summon, xp, fun, flyer, get_id, warnings, test]:
        handler.register(app)
        logger.info(f"✅ Registered handler: handlers.{handler.__name__}")

async def main():
    logger.info("⏰ Scheduler started.")
    scheduler.start()
    register_handlers()
    logger.info("✅ All handlers registered. Starting bot...")
    await app.start()
    await app.send_message(chat_id=6964994611, text="✅ Bot started successfully!")
    await app.idle()

    # Prevent container shutdown
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception("Unhandled error in main(): %s", e)
