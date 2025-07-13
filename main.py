# main.py

import os
import logging
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Health‐check server ────────────────────────────────────────────────────
def run_health():
    port = int(os.environ.get("PORT", "8000"))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    HTTPServer(("0.0.0.0", port), H).serve_forever()

threading.Thread(target=run_health, daemon=True).start()

# ─── Logging & ENV ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logger.info(f"🔍 Loaded ENV → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

async def main():
    # ─── Scheduler ──────────────────────────────────────────────────────────
    sched_tz = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
    scheduler = AsyncIOScheduler(timezone=timezone(sched_tz))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # ─── Bot client ─────────────────────────────────────────────────────────
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # ─── Register handlers ──────────────────────────────────────────────────
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

    # ─── Run + FloodWait‐retry loop ─────────────────────────────────────────
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            await idle()
            logger.info("🔄 Bot stopped—restarting…")
            await app.stop()
        except FloodWait as e:
            # Extract seconds to wait
            wait = getattr(e, "value", None) or getattr(e, "x", None) or 0
            logger.warning(f"🚧 FloodWait – sleeping for {wait}s before retry.")
            await asyncio.sleep(int(wait) + 1)
        except Exception:
            logger.exception("🔥 Unhandled error—restarting in 5s.")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
