# main.py

import os
import logging
import asyncio
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Load environment & configure logging ───────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ["PORT"])  # Railway injects this

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(threadName)s | %(message)s"
)
logger = logging.getLogger("SuccuBot")

logger.debug(
    f"ENV → API_ID={API_ID}, BOT_TOKEN=<…{len(BOT_TOKEN)} chars…>, "
    f"SCHED_TZ={SCHED_TZ}, PORT={PORT}"
)

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

threading.Thread(
    target=serve_health,
    daemon=True,
    name="HealthServer"
).start()

# ─── Main async entrypoint ─────────────────────────────────────────────────
async def start_health_server():
    # no-op: handled by threaded HTTPServer
    await asyncio.sleep(0)

async def run_bot(stop_event: asyncio.Event):
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
    logger.info("📢 Registering handlers…")
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    logger.debug("Registering flyer")
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # 4) Start bot
    try:
        logger.info("✅ Starting SuccuBot…")
        await app.start()
        logger.info("✅ SuccuBot started, entering idle()")
        await idle()
    except FloodWait as e:
        wait = int(getattr(e, "value", getattr(e, "x", 0)))
        logger.warning(f"🚧 FloodWait – sleeping {wait}s before retry")
        await asyncio.sleep(wait + 1)
    except Exception:
        logger.error("🔥 Exception in SuccuBot run:", exc_info=True)

    # 5) Wait for stop_event
    await stop_event.wait()
    logger.info("🛑 Stop signal received, shutting down…")

    # 6) Shutdown
    await app.stop()
    scheduler.shutdown()
    logger.info("✅ SuccuBot and scheduler shut down cleanly")

async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)

    # Run health-check (threaded) and the bot concurrently
    await asyncio.gather(
        start_health_server(),
        run_bot(stop_event),
    )

if __name__ == "__main__":
    logger.info("▶️ Launching asyncio main()")
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("💥 Fatal error in __main__")
