import os
import json
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Load environment variables from .env or Railway variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Create data folders/files if not exist
os.makedirs("data", exist_ok=True)
for fname in ["warnings.json", "xp.json", "summon.json", "flyers.json"]:
    fpath = os.path.join("data", fname)
    if not os.path.exists(fpath):
        with open(fpath, "w") as f:
            json.dump({}, f)

# Import and register all handler modules
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    fun,
    flyer
)

# Register handlers
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
fun.register(app)
flyer.register(app)

print("✅ SuccuBot is running...")
app.run()

