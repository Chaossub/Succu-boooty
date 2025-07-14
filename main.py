#!/usr/bin/env python3
import os
import sys
import signal
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 1) Simple health-check handler for ANY GET → 200 OK
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    loop = asyncio.get_event_loop()
    # run HTTPServer.serve_forever() in a thread so it doesn't block asyncio
    loop.create_task(loop.run_in_executor(None, server.serve_forever))

async def main():
    # 2) Load & validate env
    missing = [v for v in ("API_ID", "API_HASH", "BOT_TOKEN") if not os.getenv(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    API_ID   = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN= os.getenv("BOT_TOKEN")
    PORT     = int(os.getenv("PORT", "8080"))

    # 3) Start health-check
    start_health_server(PORT)
    print(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # 4) Scheduler + heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: print("💓 Heartbeat – scheduler alive"),
        trigger="interval",
        seconds=30
    )
    scheduler.start()

    # 5) Start the bot
    bot = Client(
        name="succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
    )
    await bot.start()
    print("✅ Bot started; awaiting SIGINT/SIGTERM…")

    # 6) Wait here until SIGINT or SIGTERM
    stop_evt = asyncio.Event()
    def _on_signal():
        stop_evt.set()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal)

    await stop_evt.wait()

    # 7) Graceful shutdown
    print("🔄 Shutdown initiated…")
    await bot.stop()
    scheduler.shutdown()
    print("✅ Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
