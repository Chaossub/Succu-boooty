import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client
import handlers.welcome
import handlers.help_cmd
import handlers.moderation
import handlers.federation
import handlers.summon
import handlers.xp
import handlers.fun

# Simple health-check HTTP endpoint
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()

# Register all handler modules
def register_handlers(app: Client):
    handlers.welcome.register(app)
    handlers.help_cmd.register(app)
    handlers.moderation.register(app)
    handlers.federation.register(app)
    handlers.summon.register(app)
    handlers.xp.register(app)
    handlers.fun.register(app)


def main():
    # Load credentials from env
    API_ID = int(os.environ["API_ID"])
    API_HASH = os.environ["API_HASH"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    PORT = int(os.getenv("PORT", 8080))

    # Start health-check endpoint
    start_health_server(PORT)
    print(f"🌐 Health-check listening on 0.0.0.0:{PORT}")

    # Initialize bot
    app = Client(
        "bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # Register handlers
    register_handlers(app)

    # Run the bot until interrupted
    print("✅ Starting SuccuBot…")
    app.run()
    print("🔄 SuccuBot shut down")


if __name__ == "__main__":
    main()
