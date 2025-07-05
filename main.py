import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode

# Setup basic logging to stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(asctime)s - %(message)s'
)

logger = logging.getLogger(__name__)

try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not API_HASH or not BOT_TOKEN:
        raise ValueError("API_HASH or BOT_TOKEN is missing in environment variables")

    logger.info("Environment variables loaded successfully")

except Exception as e:
    logger.error(f"Error loading environment variables: {e}")
    raise

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import handlers
try:
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
    logger.info("Handlers imported successfully")
except Exception as e:
    logger.error(f"Failed to import handlers: {e}")
    raise

# Register handlers with debug logs
try:
    welcome.register(app)
    logger.info("Registered welcome handler")

    help_cmd.register(app)
    logger.info("Registered help_cmd handler")

    moderation.register(app)
    logger.info("Registered moderation handler")

    federation.register(app)
    logger.info("Registered federation handler")

    summon.register(app)
    logger.info("Registered summon handler")

    xp.register(app)
    logger.info("Registered xp handler")

    fun.register(app)
    logger.info("Registered fun handler")

    flyer.register(app)
    logger.info("Registered flyer handler")

except Exception as e:
    logger.error(f"Error registering handlers: {e}")
    raise

logger.info("✅ SuccuBot is starting...")

app.run()
