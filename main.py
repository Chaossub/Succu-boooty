import asyncio
import logging
import os
import pkgutil
import importlib
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# ─── Load Env ────────────────────────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Initialize Client ───────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Scheduler ───────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Register Handlers ───────────────────────────────────────────────────────
def register_all_handlers(app):
    for _, module_name, _ in pkgutil.iter_modules(["handlers"]):
        module = importlib.import_module(f"handlers.{module_name}")
        if hasattr(module, "register"):
            module.register(app)
            logger.info(f"✅ Registered handler: handlers.{module_name}")

# ─── Idle Function ───────────────────────────────────────────────────────────
async def idle():
    while True:
        await asyncio.sleep(3600)

# ─── Main ────────────────────────────────────────────────────────────────────
async def main():
    register_all_handlers(app)
    logger.info("✅ All handlers registered. Starting bot...")
    await app.start()
    await idle()
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot stopped.")
