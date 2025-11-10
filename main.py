# main.py
import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode

from handlers.req_handlers import register_all

# ────────────── LOGGING ──────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("main")

# ────────────── ENVIRONMENT SETUP ──────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing one or more required environment variables: API_ID, API_HASH, BOT_TOKEN")

# ────────────── BOT INITIALIZATION ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN,
)

# ────────────── LOAD HANDLERS & RUN ──────────────
def main():
    print("✅ Starting SuccuBot...")

    # Automatically registers every handlers/*.py that exposes register(app)
    register_all(app)

    print("✅ Handlers loaded. Running bot...\n")
    app.run()
    print("❌ Bot stopped.")

# ────────────── ENTRY POINT ──────────────
if __name__ == "__main__":
    main()
