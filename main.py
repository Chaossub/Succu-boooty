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

# Import handlers (do not register yet)
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    fun,
    flyer
)

def debug_register(name, func):
    try:
        print(f"Registering {name}...")
        func(app)
        print(f"Registered {name} successfully.")
    except Exception as e:
        print(f"ERROR registering {name}: {e}")

# Register handlers with debugging
debug_register("welcome", welcome.register)
debug_register("help_cmd", help_cmd.register)
debug_register("moderation", moderation.register)
debug_register("federation", federation.register)
debug_register("summon", summon.register)
debug_register("fun", fun.register)
debug_register("flyer", flyer.register)

print("✅ SuccuBot is running...")
app.run()
