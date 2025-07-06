import os
import logging

from dotenv import load_dotenv
import pyrogram
from pyrogram import Client
from pyrogram.raw.types.chat_banned_rights import ChatBannedRights

# ─── Monkey-patch to avoid NoneType.to_bytes in Pyrogram 2.0.106 ───
_orig_write = ChatBannedRights.write
def _patched_write(self, *args, **kwargs):
    if not getattr(self, "until_date", None):
        logging.getLogger("patch").info("Monkey-patch: setting until_date → 2147483647")
        self.until_date = 2147483647
    return _orig_write(self, *args, **kwargs)
ChatBannedRights.write = _patched_write
# ───────────────────────────────────────────────────────────────────────

def main():
    # 1) configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 2) load .env
    logger.info("Loading environment variables…")
    load_dotenv()

    # 3) log pyrogram version
    logger.info(f"▶️ Running Pyrogram v{pyrogram.__version__}")

    # 4) read credentials
    API_ID   = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    BOT_TOKEN= os.getenv("BOT_TOKEN")

    # 5) init bot
    app = Client(
        "succubot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 6) now that env is loaded, import & register handlers
    from handlers import help_cmd, welcome, moderation, federation, summon, fun, flyer, xp
    help_cmd.register(app)
    welcome .register(app)
    moderation.register(app)
    federation.register(app)
    summon   .register(app)
    fun      .register(app)
    flyer    .register(app)
    xp       .register(app)

    # 7) start
    logger.info("Starting SuccuBot client…")
    app.run()

if __name__ == "__main__":
    main()
