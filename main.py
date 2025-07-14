import os
import logging
import asyncio
from dotenv import load_dotenv

from pyrogram import Client, idle
from pyrogram.enums import ParseMode

# Load environment variables
load_dotenv()
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID, API_HASH, or BOT_TOKEN in environment variables!")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")

async def runner():
    # THIS IS THE CORRECT WAY
    app = Client(
        "SuccuBot",          # <-- REQUIRED SESSION NAME!
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML,
    )

    # Register handlers
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
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app)

    logger.info("✅ SuccuBot is running...")
    async with app:
        await idle()

def main():
    asyncio.run(runner())

if __name__ == "__main__":
    main()
