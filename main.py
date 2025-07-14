#!/usr/bin/env python3
import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client, idle
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    # run in background thread so it doesn't block asyncio
    asyncio.get_event_loop().run_in_executor(None, server.serve_forever)


async def main():
    # load config
    API_ID = int(os.getenv("API_ID", "0") or 0)
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    PORT = int(os.getenv("PORT", "8080"))

    if not (API_ID and API_HASH and BOT_TOKEN):
        print("❌ Missing one of API_ID, API_HASH or BOT_TOKEN in env")
        return

    # start HTTP health‐check
    start_health_server(PORT)
    print(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # scheduler with 30s heartbeat
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: print("💓 Heartbeat – scheduler alive"),
        trigger="interval",
        seconds=30
    )
    scheduler.start()

    # create and start the bot
    bot = Client(
        name="succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        # you can add any other Client parameters here
    )

    await bot.start()
    print("✅ Bot started; awaiting messages…")

    # keep running until interrupted
    await idle()

    # graceful shutdown
    await bot.stop()
    scheduler.shutdown()
    print("✅ Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
