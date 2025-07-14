# main.py

import os
import logging
import asyncio
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from dotenv import load_dotenv
from pyrogram import Client
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
PORT      = int(os.environ["PORT"])  # Railway injects this

# Root logger at DEBUG, but silence low-level libs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(threadName)s | %(message)s"
)
# Reduce noise from Pyrogram & APScheduler
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger = logging.getLogger("SuccuBot")
logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN=<…{len(BOT_TOKEN)} chars…>, "
             f"SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Health‐check server (threaded) ─────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def serve_health():
    httpd = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Health‐check bound on 0.0.0.0:{PORT}", flush=True)
    httpd.serve_forever()

threading.Thread(target=serve_health, daemon=True, name="HealthServer").start()

# ─── Graceful shutdown event ─────────────────────────────────────────────────
stop_event = asyncio.Event()

def handle_signal(signum, frame):
    logger.info(f"Signal {signum} received, shutting down…")
    stop_event.set()

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ─── Main async entrypoint ─────────────────────────────────────────────────
async def main():
    # 1) Start scheduler + heartbeat
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    def heartbeat():
        logger.info("💓 Heartbeat – scheduler alive")
    scheduler.add_job(heartbeat, "interval", seconds=30)
    logger.debug("🩺 Heartbeat job scheduled every 30s")

    # 2) Initialize Pyrogram client
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # 3) Register handlers
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    logger.debug("Registering flyer")
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # 4) Start the bot
    try:
        logger.info("✅ Starting SuccuBot…")
        await app.start()
    except Exception:
        logger.exception("🔥 Failed to start SuccuBot")
        return

    # 5) Wait for shutdown signal
    logger.info("🛑 Awaiting SIGINT/SIGTERM to stop...")
    await stop_event.wait()

    # 6) Shutdown sequence
    logger.info("🔄 Stopping SuccuBot…")
    await app.stop()
    scheduler.shutdown()
    logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    logger.info("▶️ Entering asyncio run")
    asyncio.run(main())
