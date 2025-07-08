# handlers/flyer.py

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import logging

from pyrogram import Client, filters
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pytz import UTC

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=UTC)

# 1) Mongo setup
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI env var is required")

MONGO_DB = os.environ.get("MONGO_DB", "chaossunflowerbusiness321")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

# 2) Chat filter (only groups / supergroups / channels)
CHAT_FILTER = filters.group | filters.supergroup | filters.channel

# 3) Health server (optional)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server(port=8080):
    try:
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except OSError as e:
        logger.info(f"[flyer] health server not started (port {port} in use): {e!r}")

threading.Thread(target=run_health_server, daemon=True).start()

# 4) Helper: send flyer to a list of chat_ids
async def _post_flyer(app: Client, name: str, targets: list[int]):
    flyer = db.flyers.find_one({"name": name})
    if not flyer:
        logger.warning(f"flyer “{name}” vanished before posting")
        return

    for cid in targets:
        try:
            await app.send_photo(
                chat_id=cid,
                photo=flyer["file_id"],
                caption=flyer.get("caption", ""),
            )
        except Exception as ex:
            logger.warning(f"Failed to post flyer “{name}” to {cid}: {ex!r}")

# 5) Register commands
def register(app: Client):

    @app.on_message(filters.command("createflyer") & CHAT_FILTER)
    async def create_flyer(client, message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2 or not message.photo:
            return await message.reply_text("Usage: /createflyer <name> (with a photo attached)")

        name = parts[1]
        file_id = message.photo.file_id
        caption = message.caption or ""

        db.flyers.update_one(
            {"name": name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True,
        )
        await message.reply_text(f"✅ Flyer “{name}” saved.")

    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message):
        # expects: /scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <chat1,chat2,...>
        parts = message.text.split(maxsplit=4)
        if len(parts) < 5:
            return await message.reply_text(
                "Usage: /scheduleflyer <name> <YYYY-MM-DD> <HH:MM> <chat1,chat2,...>"
            )
        _, name, date_s, time_s, raw_chats = parts

        # parse run_date in UTC
        try:
            run_dt = datetime.fromisoformat(f"{date_s}T{time_s}")
            run_dt = UTC.localize(run_dt)
        except ValueError:
            return await message.reply_text("❌ Invalid date/time. Use YYYY-MM-DD HH:MM")

        # resolve chat identifiers
        chat_ids = []
        for tag in raw_chats.split(","):
            tag = tag.strip()
            try:
                if tag.startswith("@"):
                    info = await client.get_chat(tag)
                    chat_ids.append(info.id)
                else:
                    chat_ids.append(int(tag))
            except Exception:
                return await message.reply_text(f"❌ Could not resolve chat: {tag}")

        # store in DB
        try:
            db.flyers.update_one(
                {"name": name},
                {"$set": {"next_run": run_dt, "targets": chat_ids}},
                upsert=False,
            )
        except PyMongoError as e:
            return await message.reply_text(f"❌ DB error: {e}")

        # schedule job
        job_id = f"flyer-{name}-{int(run_dt.timestamp())}"
        scheduler.add_job(
            _post_flyer,
            "date",
            run_date=run_dt,
            args=[client, name, chat_ids],
            id=job_id,
        )

        await message.reply_text(
            f"✅ Scheduled flyer “{name}” on {run_dt.isoformat()} for {len(chat_ids)} chat(s)."
        )

    @app.on_message(filters.command("cancelflyer") & CHAT_FILTER)
    async def cancel_flyer(client, message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /cancelflyer <name>")

        name = parts[1]
        # remove any pending job(s)
        jobs = [j for j in scheduler.get_jobs() if j.id.startswith(f"flyer-{name}-")]
        if not jobs:
            return await message.reply_text(f"No scheduled jobs found for “{name}”.")

        for j in jobs:
            scheduler.remove_job(j.id)

        db.flyers.update_one({"name": name}, {"$unset": {"next_run": "", "targets": ""}})

        await message.reply_text(f"🛑 Cancelled all future posts of flyer “{name}”.")

    # start scheduler once
    scheduler.start()

# expose for import
register  # noqa
