import os
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo import MongoClient
from dotenv import load_dotenv
from pyrogram import Client

# Load .env into os.environ (only if running locally; Railway injects its own env)
load_dotenv()

# Telegram credentials
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# MongoDB connection
MONGO_URI    = os.environ["MONGO_URI"]
MONGO_DBNAME = os.environ.get("MONGO_DB_NAME", "")  # e.g. "chaossunflowerbusiness321"
if not MONGO_DBNAME:
    raise RuntimeError("Please set MONGO_DB_NAME in env")
mongo_client = MongoClient(MONGO_URI)
db           = mongo_client.get_database(MONGO_DBNAME)
flyers_col   = db["flyers"]

# Chat‐ID whitelist for scheduled flyer posts
# e.g. " -10012345, -10067890 "
whitelist_env = os.environ.get("FLYER_WHITELIST", "")
FLYER_WHITELIST = [
    int(chat_id.strip())
    for chat_id in whitelist_env.split(",")
    if chat_id.strip()
]

# Set up Pyrogram & scheduler
app       = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncIOScheduler()
scheduler.start()

# Import and register handlers
# handlers/flyer.py must expose:
#   def register(app: Client, scheduler, collection, whitelist: List[int])
from handlers.flyer import register as register_flyer
register_flyer(app, scheduler, flyers_col, FLYER_WHITELIST)

# handlers/get_id.py automatically registers the /id command via decorator
import handlers.get_id  # noqa: F401

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    app.run()
