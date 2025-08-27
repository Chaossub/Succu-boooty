# main.py
import logging
import os

from pyrogram import Client
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Set up logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger("SuccuBot")

# Bot token and API credentials
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Initialize Pyrogram client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None  # we wire handlers manually
)

# Utility to wire a handler module
def wire(name: str, import_path: str):
    try:
        module = __import__(import_path, fromlist=["register"])
        if hasattr(module, "register"):
            module.register(app)
            log.info(f"✅ Wired handlers from {import_path}")
        else:
            log.warning(f"⚠️ No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)


def wire_all_handlers():
    # The ONLY /start portal
    wire("dm_foolproof", "dm_foolproof")

    # Menus + panels
    wire("handlers.menu", "handlers.menu")
    wire("handlers.contact_admins", "handlers.contact_admins")
    wire("handlers.help_panel", "handlers.help_panel")

    # dm_portal kept ONLY for callbacks (admins, links, help) — /start removed
    wire("handlers.dm_portal", "handlers.dm_portal")

    # Other features
    wire("handlers.hi", "handlers.hi")
    wire("handlers.fun", "handlers.fun")
    wire("handlers.warnings", "handlers.warnings")
    wire("handlers.moderation", "handlers.moderation")
    wire("handlers.federation", "handlers.federation")
    wire("handlers.summon", "handlers.summon")
    wire("handlers.xp", "handlers.xp")
    wire("handlers.dmnow", "handlers.dmnow")
    wire("handlers.flyer", "handlers.flyer")
    wire("handlers.flyer_scheduler", "handlers.flyer_scheduler")
    wire("handlers.schedulemsg", "handlers.schedulemsg")
    wire("handlers.exemptions", "handlers.exemptions")
    wire("handlers.req_handlers", "handlers.req_handlers")
    wire("handlers.enforce_requirements", "handlers.enforce_requirements")
    wire("handlers.welcome", "handlers.welcome")
    wire("handlers.health", "handlers.health")


if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot is starting...")
    app.run()
