import os
import logging
import signal
import threading
import socket
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
PORT      = int(os.environ["PORT"])

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN_len={len(BOT_TOKEN)}, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Health‐check handler ────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, fmt, *args):
        # suppress default logs
        pass

def start_health_servers():
    # IPv4 server
    httpd4 = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    threading.Thread(target=httpd4.serve_forever, daemon=True, name="Health-v4").start()
    # IPv6 server
    class HTTPServer6(HTTPServer):
        address_family = socket.AF_INET6
    httpd6 = HTTPServer6(("::", PORT), HealthHandler)
    threading.Thread(target=httpd6.serve_forever, daemon=True, name="Health-v6").start()
    logger.info(f"🌐 Health‐check (v4 & v6) listening on port {PORT}")

# ─── Bot + scheduler with FloodWait retry ────────────────────────────────────
async def run_bot(stop_event: asyncio.Event):
    # Scheduler + heartbeat
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")
    scheduler.add_job(lambda: logger.info("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

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
    logger.info("📢 Registering handlers…")
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # FloodWait-aware start loop
    while not stop_event.is_set():
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.info("✅ SuccuBot started")
            break
        except FloodWait as e:
            secs = max(1, int(getattr(e, "value", getattr(e, "x", 0))))
            logger.warning(f"🚧 FloodWait on start – retrying in {secs}s")
            await asyncio.sleep(secs)
        except Exception:
            logger.exception("🔥 Error on start – retrying in 5s")
            await asyncio.sleep(5)

    # Await termination
    if not stop_event.is_set():
        logger.info("🛑 Bot running; awaiting stop signal…")
        await stop_event.wait()
        logger.info("🔄 Stop signal received; shutting down…")
        await app.stop()

    scheduler.shutdown()
    logger.info("✅ SuccuBot and scheduler shut down cleanly")

# ─── Entrypoint ─────────────────────────────────────────────────────────────
async def main():
    # fire up dual-stack health servers
    start_health_servers()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT,  stop_event.set)

    await run_bot(stop_event)

if __name__ == "__main__":
    logger.info("▶️ Launching SuccuBot")
    asyncio.run(main())
