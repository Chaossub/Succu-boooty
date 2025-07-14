import asyncio
import logging
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Health check handler
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server(port: int):
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 Health-check v4 listening on 0.0.0.0:{port}")
    return server

async def main():
    # Read env or config here
    API_ID = int(os.getenv('API_ID', ''))
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    PORT = int(os.getenv('PORT', '8080'))

    # Start health server
    health_server = start_health_server(PORT)

    # Start scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logger.info('💓 Heartbeat – scheduler alive'), 'interval', seconds=30)
    scheduler.start()

    # Initialize bot
    app = Client('bot', api_id=API_ID, bot_token=BOT_TOKEN)
    await app.start()
    logger.info('✅ Bot started; awaiting SIGINT/SIGTERM…')

    # Wait for shutdown signal
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

    # Shutdown
    logger.info('🔄 Shutdown initiated…')
    scheduler.shutdown()
    await app.stop()
    health_server.shutdown()
    logger.info('✅ Shutdown complete')

if __name__ == '__main__':
    asyncio.run(main())

