import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters
from pyrogram.types import Message

from pymongo import MongoClient

# ─── Health server ─────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
    except OSError as e:
        print(f"[flyer] health server not started (port {port} in use): {e!r}")
        return
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()


# ─── MongoDB setup ─────────────────────────────────────────────────────
MONGO_URI    = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")
if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI and MONGO_DBNAME must both be set")

mongo_client = MongoClient(MONGO_URI)
db           = mongo_client[MONGO_DBNAME]
flyers_col   = db["flyers"]


# ─── Scheduler ─────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()
scheduler.start()


# ─── Command Handlers ──────────────────────────────────────────────────
def register(app):
    @app.on_message(filters.command("createflyer") & filters.group)
    async def create_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /createflyer <name>")
        name = parts[1].strip()
        flyers_col.insert_one({
            "chat_id": message.chat.id,
            "name": name,
            "media": [],
            "scheduled": []
        })
        await message.reply_text(f"✅ Flyer '{name}' created.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        docs = flyers_col.find({"chat_id": message.chat.id})
        names = [d["name"] for d in docs]
        if not names:
            return await message.reply_text("No flyers found.")
        await message.reply_text("📋 Flyers:\n" + "\n".join(names))

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /deleteflyer <name>")
        name = parts[1].strip()
        res = flyers_col.delete_one({
            "chat_id": message.chat.id,
            "name": name
        })
        if res.deleted_count:
            await message.reply_text(f"🗑️ Deleted flyer '{name}'.")
        else:
            await message.reply_text(f"No flyer named '{name}'.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            return await message.reply_text("Usage: /scheduleflyer <name> YYYY-MM-DD HH:MM")
        name, date_str, time_str = parts[1], parts[2], parts[3]
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(f"{date_str}T{time_str}")
        except ValueError:
            return await message.reply_text("❌ Invalid date/time. Use YYYY-MM-DD HH:MM")
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply_text(f"No flyer named '{name}'.")
        def send_flyer():
            app.send_photo(chat_id=message.chat.id, photo=flyer["media"][-1])
        job = scheduler.add_job(send_flyer, "date", run_date=dt)
        flyers_col.update_one(
            {"_id": flyer["_id"]},
            {"$push": {"scheduled": {"job_id": job.id, "run_date": dt}}}
        )
        await message.reply_text(f"⏰ Flyer '{name}' scheduled for {dt}.")

    @app.on_message(filters.command("addmedia") & filters.group)
    async def add_media(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply_text("Usage: reply to photo with /addmedia <name>")
        name = parts[1].strip()
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply_text(f"No flyer named '{name}'.")
        file_id = message.reply_to_message.photo.file_id
        flyers_col.update_one(
            {"_id": flyer["_id"]},
            {"$push": {"media": file_id}}
        )
        await message.reply_text(f"✅ Added media to '{name}'.")
