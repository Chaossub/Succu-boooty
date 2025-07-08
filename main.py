import os
import logging
import time
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Health-check HTTP server ───────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# start health‐check listener
Thread(target=run_health_server, daemon=True).start()

# ─── Load environment ────────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", 0))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Missing API_ID, API_HASH, or BOT_TOKEN")

# ─── Logging configuration ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Initialize bot client ───────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Register handlers ───────────────────────────────────────────────────
from handlers.welcome    import register as register_welcome
from handlers.help_cmd   import register as register_help
from handlers.moderation import register as register_moderation
from handlers.federation import register as register_federation
from handlers.summon     import register as register_summon
from handlers.xp         import register as register_xp
from handlers.fun        import register as register_fun
from handlers.flyer      import register as register_flyer

def main():
    logger.info("📥 Registering handlers…")
    register_welcome(app)
    register_help(app)
    register_moderation(app)
    register_federation(app)
    register_summon(app)
    register_xp(app)
    register_fun(app)
    register_flyer(app)

    logger.info("✅ SuccuBot is starting up…")
    try:
        app.run()
    except Exception:
        logger.exception("❌ app.run() exited unexpectedly")
    # If app.run() ever returns or crashes, keep the process alive
    logger.warning("⚠️ app.run() has returned — entering keep-alive loop")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
