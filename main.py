import os
import sys
import logging
from pyrogram import Client
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load environment + enforce owner
# ──────────────────────────────────────────────
load_dotenv()

# Force your Telegram ID as owner if missing
os.environ["OWNER_ID"] = "6964994611"  # Roni
os.environ.setdefault("SUPER_ADMINS", "")  # can add others later

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("SuccuBot")

# ──────────────────────────────────────────────
# Credentials
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# Helper: dynamic wiring
# ──────────────────────────────────────────────
def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", path)
        else:
            log.warning("⚠️ %s has no register(app); skipped", path)
    except Exception as e:
        log.exception("❌ Failed to wire %s: %s", path, e)

# ──────────────────────────────────────────────
# Boot order
# ──────────────────────────────────────────────
if __name__ == "__main__":
    log.info("👑 OWNER_ID set to %s", os.getenv("OWNER_ID"))

    # ========== CORE ==========
    wire("dm_foolproof")          # The ONLY /start handler
    wire("handlers.dm_ready")     # Unified DM-ready tracker, notifier, list

    # ========== SAFE HANDLERS ==========
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

    # ========== BLOCKED (legacy duplicates) ==========
    # These stay commented to prevent duplicate /start or DM-ready:
    # wire("handlers.dm_portal")
    # wire("handlers.dm_admin")
    # wire("handlers.dm_ready_admin")
    # wire("handlers.dmready_cleanup")
    # wire("handlers.dmready_watch")
    # wire("handlers.dmnow")

    log.info("🚀 SuccuBot starting…")
    app.run()

