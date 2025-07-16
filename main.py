import os
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Load env vars from .env if present
load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Initialize Pyrogram Client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import and register all handlers
from handlers import flyer, moderation, federation, fun, xp, summon, welcome, help_cmd

def main():
    print("MAIN.PY BOOTSTRAP BEGIN")
    print("Loaded environment.")
    flyer.register(app)
    moderation.register(app)
    federation.register(app)
    fun.register(app)
    xp.register(app)
    summon.register(app)
    welcome.register(app)
    help_cmd.register(app)
    app.run()

if __name__ == "__main__":
    main()
