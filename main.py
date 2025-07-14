# main.py

import os
import logging
import asyncio
from http import HTTPStatus

from dotenv import load_dotenv
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# ─── Logging & ENV ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", "8000"))

logger.info(f"🔍 ENV loaded → API_ID={API_ID}, BOT_TOKEN starts with {BOT_TOKEN[:5]}…")

# ─── Async HTTP health‐check server ─────────────────────────────────────────
async def health_server():
    server = await asyncio.start_server(
        lambda r, w: (
            # read & ignore
            asyncio.create_task(r.read(1024)),
            w.write(b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: 2\r\n"
                    b"\r\n"
                    b"OK"),
            asyncio.create_task(w.drain()),
            w.close()
        ),
        "0.0.0.0",
        PORT
    )
    logger.info(f"🌐 Health‐check listening on 0.0.0.0:{PORT}")
    async with server:
        await server.serve_forever()

# ─── Main async entrypoint ─────────────────────────────────────────────────
async def main():
    # 1) Start health server and yield so it binds immediately
    asyncio.create_task(health_server())
    await asyncio.sleep(0)  # let health_server start

    # 2) Scheduler
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # 3) Pyrogram client
    app = Client(
        "SuccuBot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        parse_mode=ParseMode.HTML
    )

    # 4) Register handlers
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

    # 5) Run + FloodWait/Retry loop
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

if __name__ == "__main__":
    asyncio.run(main())
