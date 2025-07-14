# main.py

import os
import logging
import signal
import asyncio

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ["PORT"])

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger("SuccuBot")
logging.getLogger("pyrogram").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN_len={len(BOT_TOKEN)}, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Asyncio health‐check ────────────────────────────────────────────────────
async def health_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    data = await reader.read(1024)
    if b"GET" in data:
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 2\r\n"
            b"\r\n"
            b"OK"
        )
        await writer.drain()
    writer.close()

async def start_health_server():
    server = await asyncio.start_server(health_handler, "0.0.0.0", PORT)
    logger.info(f"🌐 Health‐check listening on 0.0.0.0:{PORT}")
    async with server:
        await server.serve_forever()

# ─── Bot + Scheduler ────────────────────────────────────────────────────────
async def run_bot(stop_event: asyncio.Event):
    # Scheduler + heartbeat
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")
    scheduler.add_job(lambda: logger.info("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

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
    for mod in (welcome, help_cmd, moderation, federation, summon, xp, fun):
        logger.debug(f"Registering {mod.__name__}")
        mod.register(app)
    flyer.register(app, scheduler)
    logger.info("📢 Handlers registered")

    # FloodWait‐aware start
    while not stop_event.is_set():
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.info("✅ SuccuBot started")
            break
        except FloodWait as e:
            secs = max(1, int(getattr(e, "value", getattr(e, "x", 0))))
            logger.warning(f"🚧 FloodWait on start – retrying in {secs}s")
            await asyncio.sleep(secs)
        except Exception:
            logger.exception("🔥 Error on start – retrying in 5s")
            await asyncio.sleep(5)

    if not stop_event.is_set():
        logger.info("🛑 Bot running; waiting for stop signal…")
        await stop_event.wait()
        logger.info("🔄 Stop signal received; shutting down bot…")
        await app.stop()

    scheduler.shutdown()
    logger.info("✅ Shutdown complete")

# ─── Entrypoint ─────────────────────────────────────────────────────────────
async def main():
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT,  stop_event.set)

    await asyncio.gather(
        start_health_server(),
        run_bot(stop_event),
    )

if __name__ == "__main__":
    logger.info("▶️ Launching SuccuBot")
    asyncio.run(main())
