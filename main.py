import os
import sys
import logging
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("SuccuBot")

# ---------- Bot credentials ----------
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
    """Import a module and call its register(app) if present."""
    try:
        mod = __import__(path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", path)
        else:
            log.warning("ℹ️  %s has no register(app); skipped", path)
    except Exception as e:
        log.exception("❌ Failed to wire %s: %s", path, e)


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # IMPORTANT: Only ONE /start source and ONE DM-ready implementation.
    # ------------------------------------------------------------------
    # /start (welcome) lives ONLY here:
    wire("dm_foolproof")

    # DM-ready storage + owner tools + auto-remove on leave:
    wire("handlers.dm_ready")

    # ------------------------------------------------------------------
    # SAFE modules (must NOT register /start or DM-ready themselves)
    # ------------------------------------------------------------------
    wire("handlers.panels")
    wire("handlers.menu")              # safe; no /start
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

    # ------------------------------------------------------------------
    # DO NOT WIRE THESE (legacy/overlapping handlers):
    # ------------------------------------------------------------------
    # wire("handlers.dm_ready_admin")   # legacy DM-ready admin
    # wire("handlers.dm_portal")        # may touch /start or DM-ready
    # wire("handlers.dm_admin")         # legacy DM controls
    # wire("handlers.dmnow")            # legacy DM list/now
    # wire("handlers.dmready_cleanup")  # merged into handlers.dm_ready
    # wire("handlers.dmready_watch")    # merged into handlers.dm_ready
    # (Leave commented out to avoid duplicate logic.)

    log.info("🚀 SuccuBot starting…")
    app.run()
