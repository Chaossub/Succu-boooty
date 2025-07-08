import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# --- Chat filter: only basic groups & supergroups ---
def _is_group_chat(_, __, message: Message):
    return bool(message.chat and message.chat.type in ("group", "supergroup"))

CHAT_FILTER = filters.create(_is_group_chat)

# --- Whitelist of chats (set as comma-separated IDs in env) ---
FLYER_WHITELIST = os.getenv("FLYER_WHITELIST", "")
WHITELIST_IDS = {
    int(cid)
    for cid in (x.strip() for x in FLYER_WHITELIST.split(","))
    if cid and cid.lstrip("-").isdigit()
}

# --- MongoDB setup (env-driven) ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB_NAME")
if not MONGO_URI or not MONGO_DB:
    raise RuntimeError("MONGO_URI and MONGO_DB_NAME must be set in env")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
flyers = db.flyers

def register(app, scheduler):
    # Health-check server on HEALTH_PORT (default 8080)
    def run_health_server():
        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")

        port = int(os.getenv("HEALTH_PORT", 8080))
        try:
            HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
        except OSError:
            app.logger.warning("[flyer] health server not started (port %d in use)", port)

    threading.Thread(target=run_health_server, daemon=True).start()

    @app.on_message(CHAT_FILTER & filters.command("flyer"))
    async def add_flyer(client, message: Message):
        chat_id = message.chat.id
        if chat_id not in WHITELIST_IDS:
            return  # ignore non-whitelisted chats

        # Save flyer info to MongoDB
        flyers.insert_one({
            "chat_id": chat_id,
            "user_id": message.from_user.id if message.from_user else None,
            "text": message.text or "",
            "timestamp": message.date.timestamp()
        })
        await message.reply("✅ Flyer logged!")

    # Scheduled daily broadcast (e.g. 9:00 AM UTC)
    def broadcast_flyers():
        for chat_id in WHITELIST_IDS:
            items = list(flyers.find({"chat_id": chat_id}))
            if not items:
                continue

            lines = []
            for f in items:
                lines.append(f"- {f['text']}")
            body = "📢 Today's flyers:\n\n" + "\n".join(lines)
            try:
                app.send_message(chat_id, body)
            except Exception as e:
                app.logger.error("[flyer] failed to broadcast to %d: %s", chat_id, e)

    scheduler.add_job(broadcast_flyers, "cron", hour=int(os.getenv("FLYER_HOUR", "9")), minute=0)
