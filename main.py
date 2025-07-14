import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
import flyer

# Simple health-check HTTP server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

async def start_health_server(port: int):
    loop = asyncio.get_running_loop()
    server = HTTPServer(('', port), HealthHandler)
    # Run the blocking server in a thread
    loop.run_in_executor(None, server.serve_forever)
    print(f"🌐 Health-check listening on 0.0.0.0:{port}")

async def run_bot(api_id: int, api_hash: str, bot_token: str):
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), 'interval', seconds=30)
    scheduler.start()

    # Initialize Pyrogram client
    app = Client(
        'bot-session',
        api_id=api_id,
        api_hash=api_hash,
        bot_token=bot_token
    )

    # Register your handlers
    flyer.register(app, scheduler)

    # Start bot
    await app.start()
    print("✅ Bot started; awaiting stop signal…")
    await app.idle()
    await app.stop()
    scheduler.shutdown()

async def main():
    # Read environment variables
    API_ID = int(os.getenv('API_ID', '0'))
    API_HASH = os.getenv('API_HASH', '')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    PORT = int(os.getenv('PORT', '8080'))

    # Start health server and bot concurrently
    await start_health_server(PORT)
    await run_bot(API_ID, API_HASH, BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
