import os
import signal
import threading
import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)5s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# HTTP health-check handler
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

# Threaded HTTP server to serve health checks without blocking
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Start health-check server on IPv4
def start_health_server(port: int):
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")
    return server

# Run the Telegram bot, auto-restarting on unexpected errors
async def run_bot(api_id: int, bot_token: str):
    while True:
        try:
            logging.info("✅ Starting SuccuBot…")
            async with Client(
                "succubot_session",
                api_id=api_id,
                bot_token=bot_token,
                workdir=os.getcwd(),
                plugins=dict(root="handlers")
            ) as app:
                await app.idle()
                break
        except Exception as e:
            logging.error(f"🔥 Bot crashed: {e}. Restarting in 5s…")
            await asyncio.sleep(5)

async def main():
    # Load configuration
    api_id = int(os.getenv("API_ID", "0"))
    bot_token = os.getenv("BOT_TOKEN", "")
    port = int(os.getenv("PORT", "8000"))

    # Setup logging
    setup_logging()
    logging.debug(f"ENV → API_ID={api_id}, BOT_TOKEN_len={len(bot_token)}, PORT={port}")

    # Start health-check server
    start_health_server(port)

    # Scheduler for heartbeat logs
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logging.info("💓 Heartbeat – scheduler alive"), 'interval', seconds=30)
    scheduler.start()

    # Setup graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Launch the bot
    bot_task = asyncio.create_task(run_bot(api_id, bot_token))

    # Wait for termination signal
    await stop_event.wait()
    logging.info("🔄 Stop signal received; shutting down…")

    # Clean up
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass
    await scheduler.shutdown()
    logging.info("✅ Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
