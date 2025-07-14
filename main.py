#!/usr/bin/env python3
import os
import signal
import threading
import asyncio
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# ─── Adjust these to match your project layout ────────────────────────────────
from handlers import flyer, welcome, help_cmd, moderation, federation, summon, xp, fun

# ─── Configuration ─────────────────────────────────────────────────────────────
API_ID    = int(os.getenv("API_ID",   "0"))
API_HASH  = os.getenv("API_HASH",      "")
BOT_TOKEN = os.getenv("BOT_TOKEN",     "")
PORT      = int(os.getenv("PORT",    "8080"))

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH and BOT_TOKEN environment variables are required")

# ─── Health-check HTTP endpoint ────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port: int):
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"🌐 Health-check listening on 0.0.0.0:{port}")
    return server

# ─── Register all your Pyrogram handlers here ─────────────────────────────────
def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    flyer.register(app, scheduler)
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)

# ─── Application entrypoint ───────────────────────────────────────────────────
def main():
    # 1) start HTTP health-check
    start_health_server(PORT)

    # 2) prepare APScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

    # 3) prepare Pyrogram bot
    app = Client(
        "bot-session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 4) wire up handlers
    register_handlers(app, scheduler)

    # 5) run everything under a dedicated asyncio loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        scheduler.start()
        await app.start()
        print("✅ SuccuBot started; awaiting stop signal…")

        stop_event = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        print("🔄 Shutdown initiated…")
        scheduler.shutdown(wait=False)
        await app.stop()
        print("✅ Shutdown complete")

    try:
        loop.run_until_complete(run())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
