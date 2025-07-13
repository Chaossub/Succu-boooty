# main.py
import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ─── Load env ───────────────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

print(f"🔍 Loaded ENV → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info(f"🌐 Health-check server listening on :{port}")
    server.serve_forever()

def run_bot():
    # ─── Scheduler ──────────────────────────────────────────────────────────
    sched_tz   = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
    scheduler  = BackgroundScheduler(timezone=timezone(sched_tz))
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
    from handlers import (
        welcome,
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer,
    )
    logger.info("📢 Registering handlers…")
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

    logger.info("✅ SuccuBot is running…")
    app.run()

if __name__ == "__main__":
    # 1) Health-check on background thread
    threading.Thread(target=run_health_server, daemon=True).start()
    # 2) Bot (with scheduler) on main thread
    run_bot()
