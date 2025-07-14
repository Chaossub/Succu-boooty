#!/usr/bin/env python3
import os
import signal
import threading
import asyncio
import importlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# ─── Configuration ─────────────────────────────────────────────────────────────
API_ID    = int(os.getenv("API_ID",   "0"))
API_HASH  = os.getenv("API_HASH",      "")
BOT_TOKEN = os.getenv("BOT_TOKEN",     "")
PORT      = int(os.getenv("PORT",    "8080"))

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID, API_HASH or BOT_TOKEN environment variable")

# ─── Health-check HTTP endpoint ───────────────────────────────────────────────
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

# ─── Dynamically load your handlers (won’t crash if missing) ────────────────────
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
        print(f"✅ Loaded {module_name}")
    except ImportError:
        print(f"⚠️ Could not load {module_name}; skipping")

def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    if "flyer" in loaded_handlers:
        loaded_handlers["flyer"].register(app, scheduler)
    for key in ("welcome","help_cmd","moderation","federation","summon","xp","fun"):
        mod = loaded_handlers.get(key)
        if mod:
            mod.register(app)

# ─── Main entrypoint ────────────────────────────────────────────────────────────
def main():
    # 1) Start health-check server
    start_health_server(PORT)

    # 2) Prepare APScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), "interval", seconds=30)

    # 3) Prepare your Pyrogram bot
    app = Client("bot-session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    register_handlers(app, scheduler)

    # 4) Run everything under a dedicated asyncio loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def runner():
        scheduler.start()
        await app.start()
        print("✅ Bot started; awaiting SIGINT/SIGTERM…")

        stop_event = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()
        print("🔄 Shutdown initiated…")
        scheduler.shutdown(wait=False)
        await app.stop()
        print("✅ Shutdown complete")

    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
