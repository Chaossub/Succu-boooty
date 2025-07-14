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

# ─── Load env & configure root logging ──────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ["PORT"])  # let Railway inject this

logging.basicConfig(
    level=logging.DEBUG,  # FULL verbosity
    format="%(asctime)s | %(levelname)8s | %(name)s | %(threadName)s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
# Turn on APScheduler & Pyrogram debug logs too:
logging.getLogger("apscheduler").setLevel(logging.DEBUG)
logging.getLogger("pyrogram").setLevel(logging.DEBUG)

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN=<…{len(BOT_TOKEN)} chars…>, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── HTTP health‐check server ────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        peer = self.client_address
        logger.debug(f"Health GET from {peer}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        peer = self.client_address
        logger.debug(f"Health HEAD from {peer}")
        self.send_response(200)
        self.end_headers()

def serve_health():
    try:
        httpd = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info(f"🌐 Health‐check bound on 0.0.0.0:{PORT}")
        httpd.serve_forever()
    except Exception:
        logger.exception("Health server crashed")

threading.Thread(target=serve_health, name="HealthServer", daemon=True).start()

# ─── Graceful shutdown on SIGTERM ────────────────────────────────────────────
def handle_sigterm(signum, frame):
    logger.warning("SIGTERM received, exiting…")
    raise SystemExit()

signal.signal(signal.SIGTERM, handle_sigterm)

# ─── Main async entrypoint ───────────────────────────────────────────────────
async def main():
    # 1) Scheduler
    logger.debug("Creating AsyncIOScheduler")
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # 2) Pyrogram client
    logger.debug("Instantiating Pyrogram Client")
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # 3) Register handlers
    logger.debug("Registering handlers modules")
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    for module in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f" → {module.__name__}.register()")
        module.register(app)
    logger.debug(" → flyer.register()")
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # 4) Run loop with FloodWait handling
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.debug("→ app.start() complete, entering idle()")
            await idle()
            logger.info("🔄 idle() returned, stopping client…")
            await app.stop()
            logger.info("🔄 client stopped cleanly—will restart")
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping {secs}s")
            await asyncio.sleep(secs + 1)
        except SystemExit:
            logger.info("SystemExit—breaking main loop")
            break
        except Exception:
            logger.error("🔥 Exception in main loop:", exc_info=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        logger.info("▶️ Launching asyncio main()")
        asyncio.run(main())
    except Exception:
        logger.error("💥 Fatal error in __main__:", exc_info=True)
        traceback.print_exc()
