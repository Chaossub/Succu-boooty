import os
import logging

from dotenv import load_dotenv
import pyrogram
from pyrogram import Client

# Import your handler modules here
from handlers import help_cmd, welcome, moderation, federation, summon, fun, flyer

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # 1. Load environment variables
    logger.info("Loading environment variables...")
    load_dotenv()

    # 2. Log Pyrogram version
    logger.info(f"▶️ Running Pyrogram v{pyrogram.__version__}")

    # 3. Read required vars
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    # 4. Initialize the bot client
    app = Client(
        "succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 5. Register all your handlers
    help_cmd.register(app)
    welcome.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    fun.register(app)
    flyer.register(app)

    # 6. Start the bot
    logger.info("Starting SuccuBot client...")
    app.run()

if __name__ == "__main__":
    main()
