#!/usr/bin/env python3
import os
import sys
import asyncio
import signal
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client, idle
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
title = "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=title)
logger = logging.getLogger()

# Load environment variables
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))

# Validate required credentials
if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("The API_ID, API_HASH, and BOT_TOKEN environment variables are all required.")
    sys.exit(1)

# Health check HTTP handler (IPv4 only)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # suppress default logging
        return

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, server.serve_forever)

# Initialize the bot client
app = Client(
    "bot-session",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Scheduler for periodic tasks
def heartbeat():
    logger.info("💓 Heartbeat – scheduler alive")

scheduler = AsyncIOScheduler(timezone=os.environ.get("SCHED_TZ"))
scheduler.add_job(heartbeat, "interval", seconds=30)

# Register handlers from modules
def register_handlers():
    import handlers.welcome as welcome
    import handlers.help_cmd as help_cmd
    import handlers.moderation as moderation
    import handlers.federation as federation
    import handlers.summon as summon
    import handlers.xp as xp
    import handlers.fun as fun
    import handlers.flyer as flyer

    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register()
    logger.info("📢 Handlers registered")

# Graceful shutdown on signals
def shutdown():
    logger.info("🔄 Stop signal received; shutting down…")
    scheduler.shutdown(wait=False)
    # schedule bot stop
    asyncio.create_task(app.stop())

# Main run logic
async def run_bot():
    logger.info("✅ Starting SuccuBot…")
    await app.start()
    logger.info("✅ SuccuBot started successfully")
    await idle()
    await app.stop()
    logger.info("🛑 SuccuBot stopped")

# Entrypoint
def main():
    start_health_server()
    register_handlers()
    scheduler.start()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    try:
        loop.run_until_complete(run_bot())
    finally:
        logger.info("💥 Exiting main loop")

if __name__ == "__main__":
    main()
