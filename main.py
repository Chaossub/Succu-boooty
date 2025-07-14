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

# ─── Load environment & configure logging ───────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SCHED_TZ  = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.environ["PORT"])  # Railway will inject this

logging.basicConfig(
    level=logging.DEBUG,  # full verbosity
    format="%(asctime)s | %(levelname)8s | %(threadName)s | %(message)s"
)
logger = logging.getLogger("SuccuBot")

logger.debug(f"ENV → API_ID={API_ID}, BOT_TOKEN=<…{len(BOT_TOKEN)} chars…>, SCHED_TZ={SCHED_TZ}, PORT={PORT}")

# ─── Asyncio-based health-check server ──────────────────────────────────────
async def handle_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        data = await reader.read(1024)
        logger.debug(f"🔍 Health-check request data: {data!r}")
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 2\r\n"
            b"\r\n"
            b"OK"
        )
        await writer.drain()
    except Exception:
        logger.exception("🔴 Error in health handler")
    finally:
        writer.close()

async def start_health_server():
    server = await asyncio.start_server(handle_health, "0.0.0.0", PORT)
    logger.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")
    async with server:
        await server.serve_forever()

# ─── Bot and scheduler runner ────────────────────────────────────────────────
async def run_bot():
    # Start the scheduler
    scheduler = AsyncIOScheduler(timezone=timezone(SCHED_TZ))
    scheduler.start()
    logger.info("🔌 Scheduler started")

    # Add a heartbeat job so we know the scheduler is alive
    def heartbeat():
        logger.info("💓 Heartbeat – scheduler is alive")
    scheduler.add_job(heartbeat, "interval", seconds=30)
    logger.debug("🩺 Heartbeat job scheduled every 30s")

    # Initialize Pyrogram client
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

    # Run loop with FloodWait handling
    while True:
        try:
            logger.info("✅ Starting SuccuBot…")
            await app.start()
            logger.debug("→ app.start() complete, entering idle()")
            await idle()
            logger.info("🔄 idle() returned, stopping client…")
            await app.stop()
            logger.info("🔄 SuccuBot stopped cleanly—will restart")
        except FloodWait as e:
            secs = int(getattr(e, "value", getattr(e, "x", 0)))
            logger.warning(f"🚧 FloodWait – sleeping {secs}s before retry")
            await asyncio.sleep(secs + 1)
        except Exception:
            logger.error("🔥 Exception in bot loop:", exc_info=True)
            await asyncio.sleep(5)

# ─── Entry point ────────────────────────────────────────────────────────────
async def main():
    # Run health-check server and bot concurrently
    await asyncio.gather(
        start_health_server(),
        run_bot(),
    )

if __name__ == "__main__":
    logger.info("▶️ Launching main()")
    try:
        asyncio.run(main())
    except Exception:
        logger.error("💥 Fatal error in __main__:", exc_info=True)
