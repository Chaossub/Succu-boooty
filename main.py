import os
import sys
import logging

from dotenv import load_dotenv
import pyrogram
from pyrogram import Client
from pyrogram.raw.types.chat_banned_rights import ChatBannedRights

# ─── Monkey-patch ChatBannedRights.write to avoid NoneType.to_bytes ───
_orig_write = ChatBannedRights.write
def _patched_write(self, *args, **kwargs):
    # If no until_date, force to max int (never expire)
    if not getattr(self, "until_date", None):
        logging.getLogger("patch").info("[Monkey-patch] setting until_date → 2147483647")
        self.until_date = 2147483647
    return _orig_write(self, *args, **kwargs)
ChatBannedRights.write = _patched_write
# ───────────────────────────────────────────────────────────────────────

# Import your handlers
from handlers import help_cmd, welcome, moderation, federation, summon, fun, flyer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger()

def main():
    # 1. Load env
    logger.info("Loading environment variables...")
    load_dotenv()

    # 2. Show Pyrogram version
    logger.info(f"▶️ Running Pyrogram v{pyrogram.__version__}")

    # 3. Read creds
    API_ID   = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN= os.getenv("BOT_TOKEN")

    # 4. Create client
    app = Client(
        "succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 5. Register handlers
    help_cmd.register(app)
    welcome .register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    fun     .register(app)
    flyer   .register(app)

    # 6. Start
    logger.info("Starting SuccuBot client...")
    app.run()

if __name__ == "__main__":
    main()

