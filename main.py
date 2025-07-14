import os
import logging
import signal
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import asyncio
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Load env ────────────────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ.get("PORT", "8000"))

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN_len={len(BOT_TOKEN)}, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Health‐check handler & server ───────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, fmt, *args):
        pass  # silence access logs

class HealthHTTPServer(HTTPServer):
    allow_reuse_address = True

def start_health_server():
    try:
        srv = HealthHTTPServer(("0.0.0.0", PORT), HealthHandler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True, name="Health-v4")
        thread.start()
        logger.info(f"🌐 Health‐check v4 listening on 0.0.0.0:{PORT}")
    except OSError as e:
        logger.error(f"❌ Failed to bind health‐check on 0.0.0.0:{PORT}: {e}")
        raise

# ─── Bot + scheduler with FloodWait retry ────────────────────────────────────
async def run_bot(stop_event: asyncio.Event):
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")
    scheduler.add_job(lambda: logger.info("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # Register handlers
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    logger.info("📢 Registering handlers…")
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"→ {mod.__name__}")
        mod.register(app)
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # FloodWait-aware startup
    while not stop_event.is_set():
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.info("✅ SuccuBot started")
            break
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0))) or 10
            logger.warning(f"🚧 FloodWait – retrying in {secs}s")
            await asyncio.sleep(secs)
        except Exception:
            logger.exception("🔥 Error on start – retrying in 5s")
            await asyncio.sleep(5)

    if stop_event.is_set():
        return

    logger.info("🛑 Bot running; awaiting stop signal…")
    await stop_event.wait()
    logger.info("🔄 Stop signal received; shutting down…")
    await app.stop()

    scheduler.shutdown()
    logger.info("✅ SuccuBot and scheduler shut down cleanly")

# ─── Entrypoint ─────────────────────────────────────────────────────────────
async def main():
    start_health_server()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT,  stop_event.set)

    await run_bot(stop_event)

if __name__ == "__main__":
    logger.info("▶️ Launching SuccuBot")
    asyncio.run(main())
