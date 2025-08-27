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
    try:
        module = __import__(import_path, fromlist=["register"])
        if hasattr(module, "register"):
            module.register(app)
            log.info(f"✅ Wired: {import_path}")
        else:
            log.warning(f"⚠️ No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

# ---------- Handlers ----------
def wire_all_handlers():
    # The ONLY /start portal (do not wire any other module that registers /start)
    wire("dm_foolproof")

    # Menus UI + per-model custom menu text + panels
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # Requirements suite (original repo)
    wire("handlers.enforce_requirements")

    # DM “test” to DM-ready users missing requirements
    wire("handlers.test_send")

    # Admin-only one-shot full command list (/bloop)
    wire("handlers.bloop")

    # IMPORTANT: Do NOT wire handlers.dm_portal (duplicates callbacks & /start)
    # Remove any previous wiring of that module.

    # ---- Optional extras (uncomment only if you actually use them) ----
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
    # wire("handlers.welcome")
    # wire("handlers.health")
    # wire("handlers.fun")
    # wire("handlers.hi")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()
