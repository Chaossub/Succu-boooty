#!/usr/bin/env python3
import os
import signal
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
import flyer

# Configure logging
tlogging_format = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=tlogging_format)

# Environment variables
PORT = int(os.getenv("PORT", "8080"))
API_ID = int(os.getenv("API_ID", ""))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

# Start a simple HTTP server in a thread for health checks
def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

# Heartbeat job
def heartbeat():
    logging.info("💓 Heartbeat – scheduler alive")

async def runner():
    # Launch health-check server
    Thread(target=start_health_server, daemon=True).start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, 'interval', seconds=30)
    scheduler.start()
    logging.info("🗓️ Scheduler started")

    # Telegram bot client
    app = Client(api_id=API_ID, bot_token=BOT_TOKEN)
    # Register additional handlers/tasks
    flyer.register(app, scheduler)

    # Start bot
    await app.start()
    logging.info("✅ Bot started; awaiting shutdown signal…")

    # Wait for termination
    stop_evt = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_evt.set)
    await stop_evt.wait()

    # Shutdown
    logging.info("🔄 Shutdown initiated…")
    await app.stop()
    scheduler.shutdown()

def main():
    asyncio.run(runner())

if __name__ == "__main__":
    main()
