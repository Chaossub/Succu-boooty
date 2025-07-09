import os
import logging
import threading
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn

# ─── Logging Setup ────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Load Env ─────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))

app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, parse_mode=ParseMode.HTML)

# ─── FastAPI Health Server ────────────────────────────────
api = FastAPI()

@api.get("/")
def healthcheck():
    return {"status": "ok"}

def run_health_server():
    uvicorn.run(api, host="0.0.0.0", port=PORT, log_level="info")

# ─── Scheduler ─────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "UTC"))
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Register Handlers ─────────────────────────────────────
def register_handlers():
    try:
        import pkgutil
        import handlers

        for _, modname, _ in pkgutil.iter_modules(handlers.__path__):
            mod = __import__(f"handlers.{modname}", fromlist=["register"])
            if hasattr(mod, "register"):
                mod.register(app)
                logger.info(f"✅ Registered handler: handlers.{modname}")
    except Exception as e:
        logger.error(f"❌ Error registering handlers: {e}", exc_info=True)

# ─── Main Run ──────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # Start FastAPI health server in background
        threading.Thread(target=run_health_server, daemon=True).start()
        logger.info("✅ Health server running. Starting bot...")

        register_handlers()

        app.run()
    except Exception as e:
        logger.error(f"❌ Fatal error in main loop: {e}", exc_info=True)
