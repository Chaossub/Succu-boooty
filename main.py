#!/usr/bin/env python3
import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client

# Import your handler modules so they register their callbacks
import handlers.welcome
import handlers.help_cmd
import handlers.moderation
import handlers.federation
import handlers.summon
import handlers.xp
import handlers.fun

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port: int):
    httpd = HTTPServer(('0.0.0.0', port), HealthHandler)
    httpd.serve_forever()

async def main():
    # Load config from environment
    API_ID = int(os.environ['API_ID'])
    BOT_TOKEN = os.environ['BOT_TOKEN']
    PORT = int(os.environ.get('PORT', 8080))

    # Start health endpoint in background thread
    health_thread = Thread(target=start_health_server, args=(PORT,), daemon=True)
    health_thread.start()

    # Start scheduler for heartbeat or other jobs
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: print("💓 Heartbeat – scheduler alive"), 'interval', seconds=30)
    scheduler.start()

    # Initialize and run bot
    app = Client('bot_session', api_id=API_ID, bot_token=BOT_TOKEN)
    await app.start()
    print("✅ SuccuBot started; awaiting events…")

    # Keep running until interrupted
    stop_event = asyncio.Event()
    await stop_event.wait()

if __name__ == '__main__':
    asyncio.run(main())
