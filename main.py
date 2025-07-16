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

# Import all handler modules so their @app.on_message hooks register
import handlers.flyer
import handlers.moderation
import handlers.federation
import handlers.fun
import handlers.xp
import handlers.summon
import handlers.welcome
import handlers.help_cmd

if __name__ == "__main__":
    print("MAIN.PY BOOTSTRAP BEGIN")
    print("Loaded environment.")
    app.run()
