#!/usr/bin/env python3
import os
import signal
import threading
import asyncio
import importlib
import logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# ─── 0) Turn down debug chatter ────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)7s | %(name)s | %(message)s",
    level=logging.INFO,
)
# Silence Pyrogram internals (they default to DEBUG)
logging.getLogger("pyrogram.session").setLevel(logging.INFO)
logging.getLogger("pyrogram.connection").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# ─── 1) Configuration ─────────────────────────────────────────────────────────
API_ID    = int(os.getenv("API_ID",   "0"))
API_HASH  = os.getenv("API_HASH",      "")
BOT_TOKEN = os.getenv("BOT_TOKEN",     "")
PORT      = int(os.getenv("PORT",    "8080"))

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID, API_HASH or BOT_TOKEN environment variable")

# ─── 2) Health-check HTTP endpoint ────────────────────────────────────────────
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
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")
    return server

# ─── 3) Dynamically load handler modules ────────────────────────────────────────
handler_specs = [
    ("handlers.flyer",    "flyer"),
    ("handlers.welcome",  "welcome"),
    ("handlers.help_cmd", "help_cmd"),
    ("handlers.moderation","moderation"),
    ("handlers.federation","federation"),
    ("handlers.summon",   "summon"),
    ("handlers.xp",       "xp"),
    ("handlers.fun",      "fun"),
]
loaded_handlers = {}
for module_name, key in handler_specs:
    try:
        loaded_handlers[key] = importlib.import_module(module_name)
        logging.info(f"✅ Loaded {module_name}")
    except ImportError:
        logging.warning(f"⚠️  Could not load {module_name}; skipping")

def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    if "flyer" in loaded_handlers:
        loaded_handlers["flyer"].register(app, scheduler)
    for key in ("welcome","help_cmd","moderation","federation","summon","xp","fun"):
        mod = loaded_handlers.get(key)
        if mod:
            mod.register(app)

# ─── 4) Main entrypoint ────────────────────────────────────────────────────────
def main():
    # Start health-check server
    start_health_server(PORT)

    # Prepare APScheduler with a simple heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logging.info("💓 Heartbeat – scheduler alive"),
                      "interval", seconds=30)

    # Prepare your Pyrogram bot
    app = Client("bot-session",
                 api_id=API_ID,
                 api_hash=API_HASH,
                 bot_token=BOT_TOKEN)

    register_handlers(app, scheduler)

    # Run everything under its own asyncio loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        scheduler.start()
        await app.start()
        logging.info("✅ Bot started; awaiting SIGINT/SIGTERM…")

        stop_event = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        logging.info("🔄 Shutdown initiated…")
        scheduler.shutdown(wait=False)
        await app.stop()
        logging.info("✅ Shutdown complete")

    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
