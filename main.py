#!/usr/bin/env python3
import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# Simple HTTP health check
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

# Launch HTTP server in background thread
def start_health_server(port: int):
    server = HTTPServer(("", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"🌐 Health-check listening on 0.0.0.0:{port}")

# Async entrypoint for the bot
async def run_bot():
    API_ID = int(os.getenv('API_ID', '0'))
    API_HASH = os.getenv('API_HASH', '')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')

    if not API_ID or not API_HASH or not BOT_TOKEN:
        raise RuntimeError("API_ID, API_HASH and BOT_TOKEN must be set in env")

    app = Client(
        "succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    await app.start()
    print("✅ SuccuBot started")
    # Block forever, until terminated
    await asyncio.Event().wait()
    await app.stop()

# Main launcher
async def main():
    # Start HTTP health-check
    port = int(os.getenv('PORT', '8080'))
    start_health_server(port)

    # Start heartbeat scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), 'interval', seconds=30)
    scheduler.start()

    # Run bot
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())
