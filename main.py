import os
import logging
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Load environment ───────────────────────────────────────────────────
load_dotenv()
API_ID    = int(os.getenv("API_ID", 0))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Missing API_ID, API_HASH, or BOT_TOKEN in environment")

# ─── Logging configuration ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.DEBUG     # ← switched to DEBUG for handler tracing
)
logger = logging.getLogger(__name__)

# ─── Initialize bot client ──────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Register all handler modules ────────────────────────────────────────
from handlers.welcome    import register as register_welcome
from handlers.help_cmd   import register as register_help
from handlers.moderation import register as register_moderation
from handlers.federation import register as register_federation
from handlers.summon     import register as register_summon
from handlers.xp         import register as register_xp
from handlers.fun        import register as register_fun
from handlers.flyer      import register as register_flyer

def main():
    logger.debug("📥 Registering all handlers")
    register_welcome(app)
    register_help(app)
    register_moderation(app)
    register_federation(app)
    register_summon(app)
    register_xp(app)
    register_fun(app)
    register_flyer(app)

    logger.debug("✅ SuccuBot is starting up...")
    app.run()
    logger.debug("🛑 SuccuBot has stopped")

if __name__ == "__main__":
    main()
