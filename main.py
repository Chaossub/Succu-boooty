# main.py

import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

# ─── Health‐check server ────────────────────────────────────────────────────
def run_health():
    port = int(os.environ.get("PORT", "8000"))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    server = HTTPServer(("0.0.0.0", port), H)
    logging.getLogger().info(f"🌐 Health‐check on :{port}")
    server.serve_forever()

threading.Thread(target=run_health, daemon=True).start()

# ─── Load environment ───────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

print(f"🔍 Loaded ENV → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

# ─── Logging setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Initialize scheduler ───────────────────────────────────────────────────
sched_tz   = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
scheduler  = BackgroundScheduler(timezone=timezone(sched_tz))
scheduler.start()
logger.info("🔌 Scheduler started")

# ─── Initialize bot client ──────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Register handlers ──────────────────────────────────────────────────────
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

# ─── Run ────────────────────────────────────────────────────────────────────
logger.info("✅ SuccuBot is running…")
app.run()
