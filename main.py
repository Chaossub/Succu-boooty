# main.py

import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Logging & ENV ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", "8000"))

logger.info(f"🔍 ENV loaded → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

# ─── Health‐check server ────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"🌐 Health‐check listening on 0.0.0.0:{PORT}")
    server.serve_forever()

# ─── Bot + Scheduler in thread ──────────────────────────────────────────────
def run_bot_thread():
    asyncio.run(async_main())

async def async_main():
    # 1) Scheduler
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # 2) Client
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
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

    # 4) Run + FloodWait/Retry loop
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            await idle()
            logger.info("🔄 SuccuBot stopped—restarting…")
            await app.stop()
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping {secs}s before retry")
            await asyncio.sleep(secs + 1)
        except Exception:
            logger.exception("🔥 Unhandled error—waiting 5s then retry")
            await asyncio.sleep(5)

if __name__ == "__main__":
    # 1) Launch health‐check in main thread
    run_health_server() if threading.current_thread() is threading.main_thread() else None

    # 2) Start bot in background thread
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()

    # 3) Keep main thread alive serving health
    bot_thread.join()
