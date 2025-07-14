#!/usr/bin/env python3
import os
import signal
import threading
import asyncio
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# adjust these imports if your modules live elsewhere
from handlers import flyer, welcome, help_cmd, moderation, federation, summon, xp, fun

# ─── Configuration ──────────────────────────────────────────────────────────────
API_ID   = int(os.getenv("API_ID",   "0"))
API_HASH = os.getenv("API_HASH",      "")
BOT_TOKEN= os.getenv("BOT_TOKEN",     "")
PORT     = int(os.getenv("PORT",    "8080"))

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set")

# ─── Health-check HTTP server ──────────────────────────────────────────────────
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
    return server  # if you ever want to shutdown: server.shutdown()

# ─── Handler registration ───────────────────────────────────────────────────────
def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    flyer.register(app, scheduler)
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    # 1) start health endpoint
    start_health_server(PORT)

    # 2) prepare scheduler (heartbeat every 30s)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

    # 3) prepare your bot client
    app = Client(
        "bot-session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    register_handlers(app, scheduler)

    # 4) run everything under asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        scheduler.start()               # start APScheduler on this loop
        await app.start()              # connect the bot
        print("✅ SuccuBot started; awaiting stop signal…")

        stop = asyncio.Event()
        # on SIGINT/SIGTERM, set stop event
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        await stop.wait()
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
