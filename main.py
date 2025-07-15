import os
import logging
from dotenv import load_dotenv

print("MAIN.PY BOOTSTRAP BEGIN")
logging.basicConfig(level=logging.INFO)
load_dotenv()
print("Loaded environment.")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

scheduler = AsyncIOScheduler(timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))

def register_all_handlers():
    from handlers import (
        welcome,
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer,
        flyer_scheduler,
    )
    logging.info("Imported all handler modules.")
    welcome.register(app)
    help_cmd.re_
