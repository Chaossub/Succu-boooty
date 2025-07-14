import os
import asyncio
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
# Import your handler modules
from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer

# Health-check HTTP handler
def start_health_server(port: int):
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/', '/health'):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
            else:
                self.send_response(404)
                self.end_headers()

    server = ThreadingHTTPServer(('0.0.0.0', port), HealthHandler)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, server.serve_forever)
    return server

async def run_bot(api_id: int, api_hash: str, bot_token: str):
    app = Client(
        "bot_session",
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token
    )
    await app.start()
    await app.idle()
    await app.stop()


def register_handlers(app: Client, scheduler: AsyncIOScheduler):
    welcome.register(app)
    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    flyer.register(app, scheduler)


def main():
    # Load config
    api_id = int(os.getenv('API_ID', '0'))
    api_hash = os.getenv('API_HASH')
    bot_token = os.getenv('BOT_TOKEN')
    if not api_id or not api_hash or not bot_token:
        raise RuntimeError('API_ID, API_HASH and BOT_TOKEN must be set in environment')
    port = int(os.getenv('PORT', '8000'))
    tz = os.getenv('SCHED_TZ', 'UTC')

    # Start health-check
    print(f"🌐 Health-check listening on 0.0.0.0:{port}")
    # must be in event loop, so start minimal loop here
    loop = asyncio.get_event_loop()
    start_health_server(port)

    # Scheduler
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(lambda: print('💓 Heartbeat – scheduler alive'),
                      trigger='interval', seconds=30, id='heartbeat')
    scheduler.start()

    # Register handlers
    register_handlers(Client, scheduler)

    # Graceful shutdown on signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)

    # Run bot
    try:
        loop.run_until_complete(run_bot(api_id, api_hash, bot_token))
    finally:
        scheduler.shutdown()


if __name__ == '__main__':
    main()
