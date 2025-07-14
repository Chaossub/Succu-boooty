import os
import signal
import asyncio
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun
import handlers.flyer as flyer
from pyrogram import Client

# Validate essential env vars
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "8080"))

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise RuntimeError("API_ID, API_HASH and BOT_TOKEN must be set")

# Instantiate Pyrogram client
app = Client(
    "succubot_session",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Health check server
async def handle_health(request):
    return web.Response(text="OK")

async def start_health_server():
    srv = web.Application()
    srv.router.add_get('/', handle_health)
    runner = web.AppRunner(srv)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

# Scheduler and heartbeat
scheduler = AsyncIOScheduler()

def heartbeat():
    print("💓 Heartbeat – scheduler alive")

# Register handlers
def register_handlers():
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)

# Graceful shutdown
def shutdown():
    print("🔄 Stop signal received; shutting down…")
    scheduler.shutdown(wait=False)
    asyncio.create_task(app.stop())

async def main():
    # Start health server
    await start_health_server()

    # Start scheduler and jobs
    scheduler.add_job(heartbeat, 'interval', seconds=30, id='heartbeat')
    scheduler.start()
    print("✅ Scheduler started and heartbeat scheduled every 30s")

    # Register handlers
    register_handlers()
    print("✅ Handlers registered")

    # Start bot
    print("✅ Starting SuccuBot…")
    await app.start()
    print("✅ SuccuBot started; awaiting stop signal…")

    # Keep running until stopped
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, shutdown)
    await stop_event.wait()

if __name__ == '__main__':
    asyncio.run(main())
