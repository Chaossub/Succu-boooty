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
    """Import module and call register(app) if present. Logs on failure, keeps going."""
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
    # The ONLY /start portal — keep just this one to prevent duplicates.
    wire("dm_foolproof")

    # Core UI & panels
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # Requirements / Ops
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")

    # DM tools
    wire("handlers.dmnow")
    wire("handlers.dm_admin")

    # Schedulers & Flyers
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")

    # Moderation & Federation
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")

    # Summons / XP / Fun / Misc
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.hi")
    wire("handlers.warmup")
    wire("handlers.health")
    wire("handlers.welcome")

    # Admin utilities
    wire("handlers.bloop")
    wire("handlers.whoami")  # safe to keep if you add whoami.py

    # ❌ DO NOT wire the old portal; it duplicates /start
    # wire("handlers.dm_portal")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()
