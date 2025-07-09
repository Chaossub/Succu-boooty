import os
import logging
import pkgutil
import importlib
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# ─── Load Environment ─────────────────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Initialize Bot ──────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Start Scheduler ─────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Register Handlers ───────────────────────────────────────────────────────
def register_all_handlers(bot):
    for _, module_name, _ in pkgutil.iter_modules(["handlers"]):
        module = importlib.import_module(f"handlers.{module_name}")
        if hasattr(module, "register"):
            module.register(bot)
            logger.info(f"✅ Registered handler: handlers.{module_name}")

# ─── Run Bot ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    register_all_handlers(app)
    logger.info("✅ All handlers registered. Starting bot...")
    app.run()
