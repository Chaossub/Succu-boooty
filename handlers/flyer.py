import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from pymongo import MongoClient
from pyrogram import filters, Client
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

# ─── ENV / DB SETUP ────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")
if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI and MONGO_DBNAME must be set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DBNAME]
flyers_col = db.flyers

FLYER_WHITELIST = os.getenv("FLYER_WHITELIST", "")
# parse CSV of chat-IDs into a set of ints
WHITELISTED_CHAT_IDS = {
    int(cid.strip())
    for cid in FLYER_WHITELIST.split(",")
    if cid.strip()
}

# ─── CHAT FILTER ──────────────────────────────────────────────────────────────

# only allow group-type chats (includes supergroups) & channels
CHAT_FILTER = filters.chat_type.groups  # matches both basic groups & supergroups
# if you also want channels, use:
# CHAT_FILTER = filters.chat_type.groups | filters.chat_type.channels

# ─── HEALTH SERVER ────────────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except OSError as e:
        # already in use → skip
        print(f"[flyer] health server not started (port {port} in use): {e!r}")

threading.Thread(target=run_health_server, daemon=True).start()

# ─── BOT / SCHEDULER SETUP ────────────────────────────────────────────────────

app = Client("flyer_bot")
scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "UTC"))

def post_scheduled_flyers():
    now = datetime.utcnow()
    for flyer in flyers_col.find({"when": {"$lte": now}, "posted": False}):
        chat_id = flyer["chat_id"]
        if chat_id not in WHITELISTED_CHAT_IDS:
            continue

        app.send_message(chat_id, flyer["text"], **flyer.get("options", {}))
        flyers_col.update_one({"_id": flyer["_id"]}, {"$set": {"posted": True}})

scheduler.add_job(post_scheduled_flyers, "interval", minutes=1)
scheduler.start()

# ─── HANDLER REGISTER ─────────────────────────────────────────────────────────

def register():
    @app.on_message(CHAT_FILTER & filters.command("flyer"))
    def schedule_flyer(client, message):
        """
        Usage: /flyer YYYY-MM-DD HH:MM Your message here...
        """
        try:
            _, date_str, time_str, *text = message.text.split()
            dt = datetime.fromisoformat(f"{date_str}T{time_str}")
        except Exception:
            return message.reply("Usage: `/flyer YYYY-MM-DD HH:MM Your message...`", quote=True)

        flyers_col.insert_one({
            "chat_id": message.chat.id,
            "when": dt,
            "text": " ".join(text),
            "options": {},
            "posted": False
        })
        message.reply(f"Scheduled flyer for {dt.isoformat()}", quote=True)

# ─── EXPORT ───────────────────────────────────────────────────────────────────

register()
app.run()
