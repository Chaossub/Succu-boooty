import os
import logging
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn

# ─── Setup Logging ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Load .env Variables ────────────────────────────────────────
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_NAME = os.getenv("SESSION_NAME", "SuccuBot")

if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("❌ Missing required env vars: API_ID, API_HASH, or BOT_TOKEN")
    exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    logger.error("❌ API_ID must be an integer")
    exit(1)

# ─── Initialize Bot ─────────────────────────────────────────────
app = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Register Handlers ──────────────────────────────────────────
def safe_register(module_name, register_func):
    try:
        register_func(app)
        logger.info(f"✅ Registered handler: {module_name}")
    except Exception as e:
        logger.exception(f"❌ Failed to register handler {module_name}: {e}")

def register_all_handlers():
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
    safe_register("handlers.federation", federation.register)
    safe_register("handlers.flyer", flyer.register)
    safe_register("handlers.fun", fun.register)
    safe_register("handlers.get_id", get_id.register)
    safe_register("handlers.help_cmd", help_cmd.register)
    safe_register("handlers.moderation", moderation.register)
    safe_register("handlers.summon", summon.register)
    safe_register("handlers.test", test.register)
    safe_register("handlers.warnings", warnings.register)
    safe_register("handlers.welcome", welcome.register)
    safe_register("handlers.xp", xp.register)

# ─── Scheduler Setup ────────────────────────────────────────────
scheduler = BackgroundScheduler()

def start_scheduler():
    try:
        scheduler.start()
        logger.info("⏰ Scheduler started.")
    except Exception as e:
        logger.exception(f"❌ Failed to start scheduler: {e}")

# ─── FastAPI Health Server ──────────────────────────────────────
api = FastAPI()

@api.get("/")
def health():
    return {"status": "ok"}

def run_fastapi():
    try:
        uvicorn.run(api, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.exception(f"❌ Failed to start health server: {e}")

# ─── Main Start ─────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("✅ Health server running. Starting bot...")

    start_scheduler()
    register_all_handlers()

    try:
        app.run()
    except Exception as e:
        logger.exception(f"❌ Bot startup failed: {e}")

    # Launch health server in parallel if needed
    # (Skip if Railway already monitors port 8000)
