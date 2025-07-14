import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

from pyrogram import Client, idle
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import your handlers; adjust path if your flyer module lives elsewhere
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    # run it in the background
    asyncio.get_event_loop().run_in_executor(None, server.serve_forever)

async def main():
    # 1) Load config from env
    API_ID = int(os.getenv("API_ID", ""))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    PORT = int(os.getenv("PORT", "8080"))

    # 2) Health‐check
    start_health_server(PORT)
    print(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # 3) Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: print("💓 Heartbeat – scheduler alive"),
        trigger="interval",
        seconds=30
    )
    scheduler.start()

    # 4) Pyrogram bot
    bot = Client(
        name="succubot",       # replaces deprecated session_name
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 5) Register all your handlers
    flyer.register(bot, scheduler)
    welcome.register(bot)
    help_cmd.register(bot)
    moderation.register(bot)
    federation.register(bot)
    summon.register(bot)
    xp.register(bot)
    fun.register(bot)

    # 6) Start
    await bot.start()
    print("✅ Bot started; awaiting messages…")

    # 7) Idle keeps the process alive until SIGINT/SIGTERM
    await idle()

    # 8) Graceful shutdown
    await bot.stop()
    scheduler.shutdown()
    print("✅ Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
