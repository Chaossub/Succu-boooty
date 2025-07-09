import os
import logging
import importlib
import pkgutil

from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from fastapi import FastAPI
import uvicorn

# ─── ENV ────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8888))  # Railway exposes port 8888

# ─── Logging ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── FastAPI Healthcheck ────────────────────────────────
app = FastAPI()

@app.get("/")
def healthcheck():
    return {"status": "ok"}

# ─── Scheduler ───────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Pyrogram Bot ────────────────────────────────────────
bot = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Register All Handlers ──────────────────────────────
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
        xp,
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
        xp,
    ]:
        try:
            module.register(bot)
            logger.info(f"✅ Registered handler: {module.__name__}")
        except Exception as e:
            logger.error(f"❌ Failed to register handler {module.__name__}: {e}")

# ─── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        logger.info("✅ Health server running. Starting bot...")

        # Start FastAPI in background
        import threading
        threading.Thread(
            target=uvicorn.run,
            kwargs={"app": app, "host": "0.0.0.0", "port": PORT},
            daemon=True
        ).start()

        # Register handlers and run the bot
        register_handlers()
        bot.run()

    except Exception as e:
        logger.exception("❌ Failed to start bot:")
