# main.py
import logging
import os

from pyrogram import Client
from dotenv import load_dotenv

# Load .env (if present)
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

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set in the environment.")

# ---------- Pyrogram client ----------
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None,  # we wire handlers manually below
)

# ---------- Utility: wire a handler module that exposes register(app) ----------
def wire(import_path: str):
    try:
        module = __import__(import_path, fromlist=["register"])
        if hasattr(module, "register"):
            module.register(app)
            log.info(f"✅ Wired: {import_path}")
        else:
            log.warning(f"⚠️  No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

# ---------- Wire all handlers here ----------
def wire_all_handlers():
    # The ONLY /start portal + links/help callbacks
    wire("dm_foolproof")

    # Menus UI (2×2 grid, uses env or IDs)
    wire("handlers.menu")

    # Admin command: /createmenu <model> <menu text>
    wire("handlers.createmenu")

    # Contact Admins + Help panels (their callbacks are triggered from dm_foolproof)
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # IMPORTANT: Do NOT wire handlers.dm_portal (it duplicates callbacks & /start)
    # If you previously wired it, remove that line from here.

    # ---- Add any other non-portal handlers you use below (optional) ----
    # wire("handlers.hi")
    # wire("handlers.fun")
    # wire("handlers.warnings")
    # wire("handlers.moderation")
    # wire("handlers.federation")
    # wire("handlers.summon")
    # wire("handlers.xp")
    # wire("handlers.dmnow")
    # wire("handlers.flyer")
    # wire("handlers.flyer_scheduler")
    # wire("handlers.schedulemsg")
    # wire("handlers.exemptions")
    # wire("handlers.req_handlers")
    # wire("handlers.enforce_requirements")
    # wire("handlers.welcome")
    # wire("handlers.health")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()
