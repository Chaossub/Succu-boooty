# main.py
import os
from pyrogram import Client
from pyrogram.enums import ParseMode

# Handlers
from handlers import panels, dm_ready

# ────────────── ENVIRONMENT SETUP ──────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

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

# ────────────── LOAD HANDLERS ──────────────
def main():
    print("✅ Starting SuccuBot...")

    # Register handler modules
    panels.register(app)
    dm_ready.register(app)

    # Add any other handler imports here (moderation, federation, etc.)
    # Example:
    # from handlers import moderation, federation, fun
    # moderation.register(app)
    # federation.register(app)
    # fun.register(app)

    print("✅ Handlers loaded. Running bot...\n")
    app.run()
    print("❌ Bot stopped.")

# ────────────── ENTRY POINT ──────────────
if __name__ == "__main__":
    main()
