import os
import sys
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import asyncio
from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
tlogging_format = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=tlogging_format)

# Load required environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8080"))

if not API_ID or not API_HASH or not BOT_TOKEN:
    logging.error("Missing one or more required environment variables: API_ID, API_HASH, BOT_TOKEN")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    logging.error("API_ID must be an integer")
    sys.exit(1)

# Simple HTTP health-check server
def start_health_server(port):
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.info(f"Health-check listening on 0.0.0.0:{port}")

async def main():
    # Start health-check server
    start_health_server(PORT)

    # Start scheduler and heartbeat job
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logging.info("💓 Heartbeat – scheduler alive"), "interval", seconds=30)
    scheduler.start()
    logging.info("Scheduler started")

    # Initialize and start the bot
    bot = Client(
        "bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )
    await bot.start()
    logging.info("✅ Bot started; awaiting messages…")

    # Keep the bot running until interrupted
    await bot.idle()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down…")
