import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# --- Aggressive dummy web server hack for Railway ---
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"Got GET request on: {self.path}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot alive.")

def start_web_server(port):
    print(f"Starting dummy web server on 0.0.0.0:{port}")
    try:
        server = HTTPServer(("0.0.0.0", port), PingHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Port {port} failed to start: {e}")

# Start web servers on all common Railway ports (8080, 3000, 5000)
for port in (8080, 3000, 5000):
    threading.Thread(target=start_web_server, args=(port,), daemon=True).start()

# --- Set logging levels ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pyrogram.session.session").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# --- Load environment ---
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- Init scheduler ---
scheduler = BackgroundScheduler(
    timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
)
scheduler.start()

# --- Init bot ---
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# --- Import & register handlers ---
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

# --- Block forever if app.run() ever returns ---
import time
print("Bot main loop finished, blocking forever.")
while True:
    time.sleep(100)
