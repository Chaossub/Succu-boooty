import os
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Load env vars from .env if present
load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# --- Import handler modules ---
import handlers.flyer
import handlers.moderation
import handlers.federation
import handlers.fun
import handlers.xp
import handlers.summon
import handlers.welcome
import handlers.help_cmd
import handlers.flyer_scheduler  # <-- NEW: Scheduler

def main():
    logging.info("MAIN.PY BOOTSTRAP BEGIN")
    # Register all handler modules
    handlers.flyer.register(app)
    handlers.moderation.register(app)
    handlers.federation.register(app)
    handlers.fun.register(app)
    handlers.xp.register(app)
    handlers.summon.register(app)
    handlers.welcome.register(app)
    handlers.help_cmd.register(app)
    handlers.flyer_scheduler.register(app)   # <-- NEW: Scheduler
    logging.info("Imported all handler modules.")
    app.run()

if __name__ == "__main__":
    main()

