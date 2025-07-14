#!/usr/bin/env python3

import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, idle
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
testing_logging_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, testing_logging_level, logging.INFO), format="%(asctime)s | %(levelname)5s | %(message)s")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

# Start a simple HTTP health-check server
def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")

async def main():
    # Environment variables
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    PORT = int(os.getenv("PORT", "8080"))

    # Launch health-check server
    start_health_server(PORT)

    # Heartbeat scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logging.info("💓 Heartbeat – scheduler alive"), "interval", seconds=30)
    scheduler.start()

    # Initialize and start the bot
    bot = Client(
        name="succubot",  # session file name
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    await bot.start()
    logging.info("✅ Bot started; awaiting messages…")

    # Idle until termination signal
    await idle()
    logging.info("🔄 Shutdown signal received; stopping…")

    # Shutdown
    await bot.stop()
    scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
