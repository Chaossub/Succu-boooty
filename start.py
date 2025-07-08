# start.py
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

from main import app, scheduler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    scheduler.start()
    print("✅ Health server running. Starting bot...")
    app.run()
