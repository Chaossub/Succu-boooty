import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Port Listener Hack to keep Railway alive ────────────────────────────────
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        print("Got a GET request on / (Railway health check?)")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot alive.")

def start_web_server():
    print("Starting dummy web server on 0.0.0.0:8080")
    server = HTTPServer(("0.0.0.0", 8080), PingHandler)
    server.serve_forever()

threading.Thread(target=start_web_server, daemon=True).start()

# ─── Set logging levels ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pyrogram.session.session").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ─── Load environment ────────────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Init scheduler ──────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(
    timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
)
scheduler.start()

# ─── Init bot ────────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Import & register handlers ──────────────────────────────────────────────
try:
    print("Registering handlers...")
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

    print("Registering welcome...")
    welcome.register(app)
    print("Registered welcome.")
    help_cmd.register(app)
    print("Registered help_cmd.")
    moderation.register(app)
    print("Registered moderation.")
    federation.register(app)
    print("Registered federation.")
    summon.register(app)
    print("Registered summon.")
    xp.register(app)
    print("Registered xp.")
    fun.register(app)
    print("Registered fun.")

    print("Registering flyer...")
    flyer.register(app, scheduler)
    print("Registered flyer.")
except Exception as e:
    print(f"🔥 Exception during handler registration: {e}")

print("✅ SuccuBot is running...")
try:
    app.run()
except Exception as e:
    print(f"🔥 Exception during app.run(): {e}")
