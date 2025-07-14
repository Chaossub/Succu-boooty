# main.py

import os
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
import logging

# ─── Load .env (for local) & read PORT ──────────────────────────────────────
load_dotenv()
PORT = int(os.environ["PORT"])  # Railway will inject the real port

# ─── Immediately bind and announce health‐check port ───────────────────────
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
    # Raw print so it goes to stdout immediately
    print(f"🌐 Health‐check bound on 0.0.0.0:{PORT}", flush=True)
    httpd.serve_forever()

threading.Thread(target=serve_health, daemon=True).start()

# ─── Configure logging ─────────────────────────────────────────────────────
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(threadName)s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN=<…{len(BOT_TOKEN)} chars…>, SCHED_TZ={SCHED_TZ}")

# ─── Graceful shutdown on SIGTERM ───────────────────────────────────────────
def handle_sigterm(*_):
    logger.warning("SIGTERM received, exiting…")
    raise SystemExit()

signal.signal(signal.SIGTERM, handle_sigterm)

# ─── Main async entrypoint ─────────────────────────────────────────────────
async def main():
    # Scheduler
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # Pyrogram client
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # Register handlers
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    logger.debug("Registering flyer")
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # Run loop with FloodWait handling
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            await idle()
            logger.info("🔄 idle() returned, stopping…")
            await app.stop()
            logger.info("🔄 SuccuBot stopped cleanly, will restart")
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping {secs}s")
            await asyncio.sleep(secs + 1)
        except SystemExit:
            logger.info("SystemExit—breaking main loop")
            break
        except Exception:
            logger.error("🔥 Exception in bot loop:", exc_info=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        logger.info("▶️ Entering asyncio.run(main())")
        asyncio.run(main())
    except Exception:
        logger.error("💥 Fatal error:", exc_info=True)
        traceback.print_exc()
