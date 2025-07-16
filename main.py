import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import handler modules
from handlers import (
    flyer,
    moderation,
    federation,
    fun,
    xp,
    summon,
    welcome,
    help_cmd
)

def main():
    logging.info("MAIN.PY BOOTSTRAP BEGIN")
    flyer.register(app)
    moderation.register(app)
    federation.register(app)
    fun.register(app)
    xp.register(app)
    summon.register(app)
    welcome.register(app)
    help_cmd.register(app)
    logging.info("Imported all handler modules.")
    app.run()

if __name__ == "__main__":
    main()
