# main.py
import logging
import os
from pyrogram import Client
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("SuccuBot")

# ---------- Bot credentials ----------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set.")

# ---------- Pyrogram client ----------
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None,  # we wire modules manually
)

# ---------- Utility ----------
def wire(import_path: str):
    """Import module and call register(app) if present."""
    try:
        mod = __import__(import_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info(f"✅ Wired: {import_path}")
        else:
            log.warning(f"⚠️ No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

# ---------- Handlers ----------
def wire_all_handlers():
    # The ONLY /start portal (keep this as the single entry)
    wire("dm_foolproof")

    # Core UI and panels
    wire("handlers.menu")            # menus + model menus
    wire("handlers.createmenu")      # /createmenu <model> <text>
    wire("handlers.contact_admins")  # contact admins callbacks (no /start)
    wire("handlers.help_panel")      # help panel buttons

    # Ops / requirements
    wire("handlers.enforce_requirements")  # reqstatus/reqremind/etc
    wire("handlers.test_send")             # /test -> DM "test" to DM-ready missing reqs

    # DM helper
    wire("handlers.dmnow")          # /dmnow -> deep link + mark DM-ready

    # Admin utilities
    wire("handlers.bloop")          # /bloop -> full command list (admin-only)
    wire("handlers.whoami")         # /whoami -> show caller's Telegram ID

    # ❌ DO NOT wire the old portal; it duplicates /start
    # wire("handlers.dm_portal")

    # Optional extras (uncomment only if you actually use them and understand overlap)
    # wire("handlers.warnings")
    # wire("handlers.moderation")
    # wire("handlers.federation")
    # wire("handlers.summon")
    # wire("handlers.xp")
    # wire("handlers.flyer")
    # wire("handlers.flyer_scheduler")
    # wire("handlers.schedulemsg")
    # wire("handlers.req_handlers")
    # wire("handlers.welcome")
    # wire("handlers.health")
    # wire("handlers.fun")
    # wire("handlers.hi")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()
