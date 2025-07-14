# main.py

import os
import logging
import threading
import signal
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Load env & read PORT ───────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ["PORT"])  # Railway injects this

# ─── Immediate threaded health-check server ─────────────────────────────────
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
    # Print so you see it at the very top of the logs
    print(f"🌐 Health-check bound on 0.0.0.0:{PORT}", flush=True)
    httpd.serve_forever()

threading.Thread(target=serve_health, daemon=True, name="HealthServer").start()

# ─── Configure logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
# Silence overly verbose libs
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger.debug(
    f"ENV → API_ID={API_ID}, BOT_TOKEN_len={len(BOT_TOKEN)}, "
    f"SCHED_TZ={SCHED_TZ}, PORT={PORT}"
)

# ─── Bot + scheduler runner ─────────────────────────────────────────────────
async def run_bot(stop_event: asyncio.Event):
    # 1) Scheduler + heartbeat
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    def heartbeat():
        logger.info("💓 Heartbeat – scheduler alive")

    scheduler.add_job(heartbeat, "interval", seconds=30)
    logger.debug("🩺 Heartbeat job scheduled every 30s")

    # 2) Pyrogram client
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # 3) Register handlers
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    logger.info("📢 Registering handlers…")
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # 4) Start the bot
    try:
        logger.info("✅ Starting SuccuBot…")
        await app.start()
    except Exception:
        logger.exception("🔥 Failed to start SuccuBot")
        return

    # 5) Wait for SIGINT/SIGTERM
    logger.info("🛑 SuccuBot running; awaiting stop signal…")
    await stop_event.wait()

    # 6) Shutdown
    logger.info("🔄 Stop signal received; shutting down SuccuBot…")
    await app.stop()
    scheduler.shutdown()
    logger.info("✅ SuccuBot and scheduler shut down cleanly")

# ─── Entrypoint ─────────────────────────────────────────────────────────────
async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT,  stop_event.set)

    await run_bot(stop_event)

if __name__ == "__main__":
    logger.info("▶️ Launching SuccuBot")
    asyncio.run(main())

