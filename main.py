# main.py

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio
import signal
import traceback

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Load env & configure logging ───────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
# Railway will inject its real port here
PORT      = int(os.environ.get("PORT", "8000"))

logging.basicConfig(
    level=logging.DEBUG,  # ← DEBUG for maximum verbosity
    format="%(asctime)s | %(levelname)8s | %(threadName)s | %(message)s"
)
logger = logging.getLogger("SuccuBot")

logger.debug(f"Environment loaded: API_ID={API_ID}, BOT_TOKEN=<{len(BOT_TOKEN)} chars>, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Health‐check server ─────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        logger.debug("Health‐check GET received")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        logger.debug("Health‐check HEAD received")
        self.send_response(200)
        self.end_headers()

def serve_health():
    try:
        httpd = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info(f"🌐 Health‐check listening on 0.0.0.0:{PORT}")
        httpd.serve_forever()
    except Exception:
        logger.exception("💥 Health‐check server crashed")

threading.Thread(target=serve_health, name="HealthServer", daemon=True).start()

# ─── Graceful shutdown capture ────────────────────────────────────────────────
def on_sigterm(*_):
    logger.info("SIGTERM received, shutting down gracefully…")
    # flush logs & exit
    raise SystemExit()

signal.signal(signal.SIGTERM, on_sigterm)

# ─── Main async entrypoint ───────────────────────────────────────────────────
async def main():
    # 1) Scheduler
    logger.debug("Initializing AsyncIOScheduler")
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # 2) Pyrogram client
    logger.debug("Creating Pyrogram Client")
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # 3) Register handlers
    logger.debug("Importing and registering handlers")
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    for module in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering handlers from {module.__name__}")
        module.register(app)
    logger.debug("Registering flyer handler")
    flyer.register(app, scheduler)
    logger.info("📢 All handlers registered")

    # 4) Run + FloodWait/Retry loop
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.debug("Client started, entering idle()")
            await idle()
            logger.info("🔄 SuccuBot idle returned—stopping…")
            await app.stop()
            logger.info("🔄 SuccuBot stopped cleanly—will restart")
        except FloodWait as e:
            wait = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping for {wait}s before retry")
            await asyncio.sleep(wait + 1)
        except SystemExit:
            logger.info("SystemExit raised—exiting main loop")
            break
        except Exception:
            logger.error("🔥 Unexpected exception in bot loop:", exc_info=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        logger.info("▶️ Launching main()")
        asyncio.run(main())
    except Exception:
        logger.error("💥 top‐level exception in __main__:", exc_info=True)
        traceback.print_exc()
