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

# ─── Load environment ──────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", "8000"))

# ─── Logging configuration ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN_len={len(BOT_TOKEN)}, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Health-check server ───────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):
        return  # suppress default logging

class HealthHTTPServer(HTTPServer):
    allow_reuse_address = True

def start_health_server():
    try:
        server = HealthHTTPServer(("0.0.0.0", PORT), HealthHandler)
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
            name="Health-v4"
        )
        thread.start()
        logger.info(f"🌐 Health-check v4 listening on 0.0.0.0:{PORT}")
    except OSError as e:
        logger.error(f"❌ Failed to bind health-check on 0.0.0.0:{PORT}: {e}")
        raise

# ─── Bot runner with scheduler and FloodWait handling ──────────────────────
async def run_bot(stop_event: asyncio.Event):
    # set up periodic heartbeat
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")
    scheduler.add_job(
        lambda: logger.info("💓 Heartbeat – scheduler alive"),
        "interval",
        seconds=30
    )

    # initialize Pyrogram
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # register handlers
    from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
    logger.info("📢 Registering handlers…")
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"→ {mod.__name__}")
        mod.register(app)
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # attempt to start, with FloodWait retries
    while not stop_event.is_set():
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.info("✅ SuccuBot started")
            break
        except FloodWait as e:
            delay = int(getattr(e, 'value', getattr(e, 'x', 0)) or 10)
            logger.warning(f"🚧 FloodWait – retrying in {delay}s")
            await asyncio.sleep(delay)
        except Exception:
            logger.exception("🔥 Error on start – retrying in 5s")
            await asyncio.sleep(5)

    # if we were asked to stop before or during startup, exit cleanly
    if stop_event.is_set():
        await app.stop()
        scheduler.shutdown()
        logger.info("✅ Shutdown before run complete")
        return

    # main loop: wait for SIGTERM/SIGINT
    logger.info("🛑 Bot running; awaiting stop signal…")
    await stop_event.wait()

    # shutdown procedure
    logger.info("🔄 Stop signal received; shutting down…")
    await app.stop()
    scheduler.shutdown()
    logger.info("✅ SuccuBot and scheduler shut down cleanly")

# ─── Entry point ────────────────────────────────────────────────────────────
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

