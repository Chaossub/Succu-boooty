import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, idle


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


def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")


async def main():
    # Basic logging setup
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s"
    )

    # Load required env vars
    try:
        API_ID = int(os.environ["API_ID"])
        API_HASH = os.environ["API_HASH"]
        BOT_TOKEN = os.environ["BOT_TOKEN"]
    except KeyError as e:
        logging.error(f"Missing environment variable: {e.args[0]}")
        return

    PORT = int(os.environ.get("PORT", "8080"))

    # Start health endpoint
    start_health_server(PORT)

    # Scheduler heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: logging.info("💓 Heartbeat – scheduler alive"),
        trigger="interval",
        seconds=30,
    )
    scheduler.start()

    # Start the bot
    app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    await app.start()
    logging.info("✅ Bot started; awaiting messages…")

    # Idle until SIGINT/SIGTERM
    await idle()

    # Graceful shutdown
    await app.stop()
    scheduler.shutdown()
    logging.info("✅ Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
