# main.py

import os
import logging
import asyncio

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Load .env & configure logging ──────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", "8000"))  # Railway will inject this

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.info(f"🔍 ENV loaded → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

# ─── Asyncio health‐check server ─────────────────────────────────────────────
async def handle_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    await reader.read(1024)  # ignore request
    writer.write(b"HTTP/1.1 200 OK\r\n"
                 b"Content-Type: text/plain\r\n"
                 b"Content-Length: 2\r\n"
                 b"\r\n"
                 b"OK")
    await writer.drain()
    writer.close()

async def start_health_server():
    server = await asyncio.start_server(handle_health, "0.0.0.0", PORT)
    logger.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")
    async with server:
        await server.serve_forever()

# ─── Bot + Scheduler ────────────────────────────────────────────────────────
async def run_bot():
    # Scheduler
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # Pyrogram client
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # Register handlers
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

    # Run + FloodWait/Retry
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            await idle()
            logger.info("🔄 SuccuBot stopped—restarting…")
            await app.stop()
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping {secs}s before retry")
            await asyncio.sleep(secs + 1)
        except Exception:
            logger.exception("🔥 Unexpected error—waiting 5s then retry")
            await asyncio.sleep(5)

# ─── Entry point ───────────────────────────────────────────────────────────
async def main():
    # Start health‐check and bot concurrently
    await asyncio.gather(
        start_health_server(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(main())
