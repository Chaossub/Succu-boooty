import os
import sys
import logging
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

# Force owner so commands work even if .env is missing
os.environ["OWNER_ID"] = "6964994611"              # Roni
os.environ.setdefault("SUPER_ADMINS", "")          # comma-separated if you add any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("SuccuBot")

API_ID    = int(os.getenv("API_ID", "0") or "0")
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME  = os.getenv("BOT_NAME", "succubot")

app = Client(
    BOT_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    in_memory=False
)

def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", path)
        else:
            log.warning("ℹ️ %s has no register(app); skipped", path)
    except Exception as e:
        log.exception("❌ Failed to wire %s: %s", path, e)

if __name__ == "__main__":
    log.info("👑 OWNER_ID = %s", os.getenv("OWNER_ID"))

    # Single /start + unified DM-ready
    wire("dm_foolproof")          # the ONLY /start
    wire("handlers.dm_ready")     # DM-ready store, list, auto-remove, ping owner

    # Safe modules (no /start & no DM-ready in these)
    wire("handlers.panels")
    wire("handlers.menu")
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.health")
    wire("handlers.bloop")
    wire("handlers.whoami")

    # Leave these UNWIRED to avoid conflicts
    # wire("handlers.dm_portal")
    # wire("handlers.dm_admin")
    # wire("handlers.dm_ready_admin")
    # wire("handlers.dmready_cleanup")
    # wire("handlers.dmready_watch")
    # wire("handlers.dmnow")

    log.info("🚀 SuccuBot starting…")
    app.run()
