import os
import asyncio
import signal
import logging
from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Optional flyer registration
try:
    from handlers.flyer import register as flyer_register
except ImportError:
    flyer_register = None


def start_health_server(port: int):
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")
    return server


async def runner():
    # Environment
    API_ID = int(os.getenv("API_ID"))
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SCHED_TZ = os.getenv("SCHED_TZ", "UTC")
    PORT = int(os.getenv("PORT", "8080"))

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    # Health check
    start_health_server(PORT)

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=SCHED_TZ)
    scheduler.add_job(
        lambda: logging.info("💓 Heartbeat – scheduler alive"),
        trigger="interval",
        seconds=30,
        id="heartbeat",
    )
    scheduler.start()

    # Flyer handlers
    if flyer_register:
        flyer_register(scheduler=scheduler)

    # Bot client
    bot = Client(
        "bot_session",
        api_id=API_ID,
        bot_token=BOT_TOKEN,
    )
    await bot.start()
    logging.info("✅ Bot started; awaiting SIGINT/SIGTERM…")

    # Wait for termination signal
    stop_evt = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_evt.set)
    await stop_evt.wait()

    # Graceful shutdown
    logging.info("🔄 Shutdown initiated…")
    await bot.stop()
    scheduler.shutdown()
    logging.info("✅ Shutdown complete")


def main():
    asyncio.run(runner())


if __name__ == "__main__":
    main()
