#!/usr/bin/env python3
import os
import sys
import signal
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# Ensure our project root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# Try importing handlers.flyer
try:
    from handlers import flyer
    HAS_FLYER = True
    logging.info("✅ handlers.flyer loaded")
except ImportError as e:
    HAS_FLYER = False
    logging.warning(f"⚠️ Could not import handlers.flyer: {e}")

# Configure logging
LOG_FMT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
log = logging.getLogger(__name__)

# Env vars
PORT = int(os.getenv("PORT", "8080"))
API_ID = int(os.getenv("API_ID", ""))     # must be set
BOT_TOKEN = os.getenv("BOT_TOKEN", "")    # must be set

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

def heartbeat():
    log.info("💓 Heartbeat – scheduler alive")

async def runner():
    # 1) Health‐check endpoint
    Thread(target=start_health_server, daemon=True).start()
    log.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # 2) Scheduler for periodic jobs
    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, 'interval', seconds=30)
    scheduler.start()
    log.info("🗓️ Scheduler started")

    # 3) Telegram bot client
    app = Client(api_id=API_ID, bot_token=BOT_TOKEN)

    # 4) Register handlers from handlers/flyer.py
    if HAS_FLYER:
        flyer.register(app, scheduler)

    # 5) Start the bot
    await app.start()
    log.info("✅ Bot started; awaiting shutdown signal…")

    # 6) Graceful shutdown on SIGINT/SIGTERM
    stop_evt = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_evt.set)
    await stop_evt.wait()

    # 7) Teardown
    log.info("🔄 Shutdown initiated…")
    await app.stop()
    scheduler.shutdown()

def main():
    asyncio.run(runner())

if __name__ == "__main__":
    main()
