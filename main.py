#!/usr/bin/env python3
import os
import signal
import threading
import logging
import asyncio
import importlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# ─── 0) Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)7s | %(name)s | %(message)s",
    level=logging.INFO,
)
# quiet Pyrogram internals & APScheduler
logging.getLogger("pyrogram.session").setLevel(logging.INFO)
logging.getLogger("pyrogram.connection").setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# ─── 1) Config ───────────────────────────────────────────────────────────────
API_ID    = int(os.getenv("API_ID",   "0"))
API_HASH  = os.getenv("API_HASH",      "")
BOT_TOKEN = os.getenv("BOT_TOKEN",     "")
PORT      = int(os.getenv("PORT",    "8080"))

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID, API_HASH or BOT_TOKEN environment variable")

# ─── 2) Health-check server ───────────────────────────────────────────────────
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
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logging.info(f"🌐 Health-check listening on 0.0.0.0:{port}")
    return server

# ─── 3) Dynamic handler loading ───────────────────────────────────────────────
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
loaded = {}
for module_name, key in handler_specs:
    try:
        loaded[key] = importlib.import_module(module_name)
        logging.info(f"✅ Loaded {module_name}")
    except ImportError:
        logging.warning(f"⚠️  Could not load {module_name}; skipping")

def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    # flyer needs both app & scheduler
    flyer_mod = loaded.get("flyer")
    if flyer_mod:
        flyer_mod.register(app, scheduler)
    # all others just need the app
    for key in ("welcome","help_cmd","moderation","federation","summon","xp","fun"):
        mod = loaded.get(key)
        if mod:
            mod.register(app)

# ─── 4) Async main ───────────────────────────────────────────────────────────
async def main():
    start_health_server(PORT)

    # scheduler + heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logging.info("💓 Heartbeat – scheduler alive"),
                      "interval", seconds=30)
    scheduler.start()

    # the bot
    app = Client("bot-session",
                 api_id=API_ID,
                 api_hash=API_HASH,
                 bot_token=BOT_TOKEN)
    register_handlers(app, scheduler)

    await app.start()
    logging.info("✅ Bot started; awaiting SIGINT/SIGTERM…")

    # wait for termination
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()

    logging.info("🔄 Shutdown initiated…")
    await app.stop()
    scheduler.shutdown(wait=False)
    logging.info("✅ Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
