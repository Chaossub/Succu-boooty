# main.py
import os, logging, sys
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "succubot")

app = Client(
    BOT_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    in_memory=False,
)

def wire(import_path: str):
    """Import a module and call register(app) if present."""
    try:
        mod = __import__(import_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", import_path)
        else:
            log.warning("ℹ️  %s has no register()", import_path)
    except ModuleNotFoundError as e:
        log.error("❌ Failed to wire %s: %s", import_path, e)
    except Exception as e:
        log.exception("❌ Failed to wire %s: %s", import_path, e)

if __name__ == "__main__":
    # Core: start + menus + admin contact + help
    wire("dm_foolproof")                  # /start, DM-ready mark, main menu
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # Requirements / reminders toolchain
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")

    # DM helper tools
    wire("handlers.dmnow")                # /dmnow deep-link button
    wire("handlers.dm_admin")             # /dmreadylist, /dmreadyclear, etc.

    # Flyers / scheduling
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")

    # Moderation suite
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")

    # Misc feature set
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.hi")
    wire("handlers.warmup")
    wire("handlers.health")

    # Group joins/leaves (separate from /start)
    wire("handlers.welcome")

    # NEW: remove DM-ready when someone leaves/kicked/banned from your group(s)
    wire("handlers.dmready_watch")

    # Admin-only command index and optional whoami
    wire("handlers.bloop")
    wire("handlers.whoami")               # optional, if present

    log.info("🚀 SuccuBot starting…")
    app.run()
