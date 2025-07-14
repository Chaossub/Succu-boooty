import os
import signal
import threading
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# Import your handler modules and flyer
import handlers.welcome as welcome
import handlers.help_cmd as help_cmd
import handlers.moderation as moderation
import handlers.federation as federation
import handlers.summon as summon
import handlers.xp as xp
import handlers.fun as fun
import flyer

# Configure logging
default_fmt = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
logging.basicConfig(level=logging.DEBUG, format=default_fmt)
logger = logging.getLogger('SuccuBot')

# Read environment
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', '8080'))

if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("Missing one of required env vars: API_ID, API_HASH, BOT_TOKEN")
    exit(1)

# Health-check HTTP handler
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/healthz'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

# Start HTTP server in background thread
def start_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

# Main bot coroutine
async def run_bot():
    # Scheduler setup
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logger.info("💓 Heartbeat – scheduler alive"), 'interval', seconds=30, id='heartbeat')
    scheduler.start()

    # Pyrogram client
    app = Client(
        "bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
    )

    # Register handlers
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

    # Start bot
    await app.start()
    logger.info("✅ SuccuBot started")

    # Wait for stop signal
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

    # Shutdown
    logger.info("🔄 Stop signal received; shutting down…")
    await app.stop()
    scheduler.shutdown()
    logger.info("✅ SuccuBot stopped cleanly")

# Entry point
def main():
    start_health_server()
    asyncio.run(run_bot())

if __name__ == '__main__':
    main()
