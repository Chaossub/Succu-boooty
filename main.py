#!/usr/bin/env python3
import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, idle

# ─── Configuration ─────────────────────────────────────────────────────────────

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")            # ← make sure this is set in your env!
BOT_TOKEN= os.getenv("BOT_TOKEN")
PORT     = int(os.getenv("PORT", 8080))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)7s | %(message)s"
)

# ─── Health‐check HTTP Server ──────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/live", "/ready"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logging.info(f"🌐 Health‐check listening on 0.0.0.0:{PORT}")

# ─── Heartbeat Job ─────────────────────────────────────────────────────────────

async def heartbeat():
    logging.info("💓 Heartbeat – scheduler alive")

# ─── Main Entrypoint ────────────────────────────────────────────────────────────

async def main():
    # 1) Start health‐check
    start_health_server()

    # 2) Schedule heartbeat every 30s
    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, "interval", seconds=30)
    scheduler.start()

    # 3) Start the bot
    app = Client(
        "succubot-session", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        bot_token=BOT_TOKEN
    )
    await app.start()
    logging.info("✅ SuccuBot started")

    # 4) Wait until Ctrl+C / SIGTERM
    await idle()

    # 5) Clean shutdown
    logging.info("🔄 Shutting down SuccuBot…")
    await app.stop()
    scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
