import logging
import sys
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

API_ID = int(sys.getenv("API_ID", "12345"))
API_HASH = sys.getenv("API_HASH", "")
BOT_TOKEN = sys.getenv("BOT_TOKEN", "")

app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


def wire_handlers(app: Client):
    """Wire baseline handlers + your modules with exception visibility."""

    # --- baseline safety handlers ---
    @app.on_message(filters.command("start") & filters.private)
    async def _fallback_start(_, m: Message):
        await m.reply_text(
            "🔥 Welcome to SuccuBot 🔥\n"
            "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
            "Use the menu button below to explore!",
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("ping") & filters.private)
    async def _ping(_, m: Message):
        await m.reply_text("Pong! 🏓")

    @app.on_message(filters.command("diag") & filters.private)
    async def _diag(_, m: Message):
        await m.reply_text(
            f"Diag ok.\nTime: {datetime.utcnow().isoformat()}Z"
        )

    @app.on_message(filters.command("traceon") & filters.private)
    async def _traceon(_, m: Message):
        logging.getLogger().setLevel(logging.DEBUG)
        await m.reply_text("Tracing enabled. Logs will be verbose.")

    # ----- helper: try handlers.pkg then fall back to root module -----
    def _import_module(name: str):
        try:
            return __import__(name, fromlist=["register"])
        except ModuleNotFoundError:
            # if asked for handlers.x and it’s actually at the repo root (x.py)
            if name.startswith("handlers."):
                alt = name.split(".", 1)[1]
                return __import__(alt, fromlist=["register"])
            raise

    # Put dm_foolproof first and reference the ROOT module name
    modules = [
        "dm_foolproof",                 # <— root-level file
        # everything else in handlers/
        "handlers.dmnow",
        "handlers.enforce_requirements",
        "handlers.exemptions",
        "handlers.federation",
        "handlers.flyer",
        "handlers.flyer_scheduler",
        "handlers.fun",
        "handlers.help_cmd",
        "handlers.help_panel",
        "handlers.hi",
        "handlers.membership_watch",
        "handlers.menu",
        "handlers.moderation",
        "handlers.req_handlers",
        "handlers.schedulemsg",
        "handlers.summon",
        "handlers.warmup",
        "handlers.warnings",
        "handlers.welcome",
        "handlers.xp",
    ]

    wired = 0
    for mod in modules:
        try:
            m = _import_module(mod)
            if hasattr(m, "register"):
                m.register(app)
                logger.info("wired: %s", mod)
                wired += 1
            else:
                logger.warning("module %s has no register()", mod)
        except Exception:
            logger.exception("Failed to wire %s", mod)

    logger.info("Handlers wired: %d module(s).", wired)


async def main():
    logger.info("Starting SuccuBot…")
    wire_handlers(app)
    await app.start()
    logger.info("SuccuBot started.")
    await idle()


if __name__ == "__main__":
    from pyrogram import idle
    asyncio.run(main())
