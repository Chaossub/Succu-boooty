# handlers/flyer.py

import os
import uuid
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message

# Only listen in groups & channels
CHAT_FILTER = filters.group | filters.channel

# Whitelisted chat IDs (comma-separated in env)
_whitelist = os.getenv("FLYER_WHITELIST", "")
WHITELIST = set(int(cid) for cid in _whitelist.split(",") if cid)

# Mongo setup
MONGO_URI    = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")
if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI and MONGO_DBNAME must be set")

mongo_client = MongoClient(MONGO_URI)
db           = mongo_client[MONGO_DBNAME]
flyers_col   = db.flyers  # collection for all flyers

# Health endpoint
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def _start_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except OSError:
        print(f"[flyer] health server not started (port {port} in use)")

threading.Thread(target=_start_health_server, daemon=True).start()


def register(app, scheduler: BackgroundScheduler):
    @app.on_message(filters.command("createflyer") & CHAT_FILTER)
    async def create_flyer(client, message: Message):
        """/createflyer <name> (with photo attached)"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not message.photo:
            return await message.reply_text(
                "Usage: /createflyer <name>\n"
                "Then attach a photo to set as the flyer."
            )
        name     = parts[1].strip()
        photo_id = message.photo.file_id
        flyer_id = str(uuid.uuid4())
        flyers_col.insert_one({
            "_id": flyer_id,
            "name": name,
            "photo_id": photo_id,
            "created_at": datetime.utcnow(),
            "chats": []
        })
        await message.reply_text(
            f"✅ Created flyer **{name}** with ID `{flyer_id}`",
            parse_mode="markdown"
        )

    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message: Message):
        """/scheduleflyer <flyer_id> YYYY-MM-DD HH:MM"""
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            return await message.reply_text(
                "Usage: /scheduleflyer <flyer_id> YYYY-MM-DD HH:MM"
            )
        flyer_id    = parts[1]
        dt_string   = parts[2]
        try:
            run_at = datetime.strptime(dt_string, "%Y-%m-%d %H:%M")
        except ValueError:
            return await message.reply_text("❌ Invalid format. Use `YYYY-MM-DD HH:MM`", parse_mode="markdown")

        chat_id = message.chat.id
        if WHITELIST and chat_id not in WHITELIST:
            return await message.reply_text("❌ This chat is not whitelisted for scheduled flyers.")

        job_id = f"{flyer_id}_{chat_id}"
        scheduler.add_job(
            func=send_flyer,
            trigger="date",
            run_date=run_at,
            args=[client, flyer_id, chat_id],
            id=job_id
        )
        # record that we want to post this flyer here
        flyers_col.update_one({"_id": flyer_id}, {"$addToSet": {"chats": chat_id}})

        await message.reply_text(
            f"⏰ Scheduled flyer `{flyer_id}` for {run_at} in this chat.",
            parse_mode="markdown"
        )

    @app.on_message(filters.command("cancelflyer") & CHAT_FILTER)
    async def cancel_flyer(client, message: Message):
        """/cancelflyer <flyer_id>"""
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            return await message.reply_text("Usage: /cancelflyer <flyer_id>")
        flyer_id = parts[1]
        chat_id  = message.chat.id
        job_id   = f"{flyer_id}_{chat_id}"

        try:
            scheduler.remove_job(job_id)
            flyers_col.update_one({"_id": flyer_id}, {"$pull": {"chats": chat_id}})
            await message.reply_text(f"❌ Canceled scheduled flyer `{flyer_id}` here.", parse_mode="markdown")
        except Exception:
            await message.reply_text(f"❌ No scheduled job found for `{flyer_id}` in this chat.", parse_mode="markdown")

    async def send_flyer(client, flyer_id: str, chat_id: int):
        """Internal: actually send the flyer photo to chat_id"""
        doc = flyers_col.find_one({"_id": flyer_id})
        if not doc:
            return
        photo_id = doc["photo_id"]
        try:
            await client.send_photo(chat_id=chat_id, photo=photo_id)
        except Exception:
            pass

    return register
