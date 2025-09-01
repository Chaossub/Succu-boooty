# main.py
import os
import sys
import logging
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
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_NAME = os.getenv("BOT_NAME", "succubot")

# One shared client for the whole bot
app = Client(
    BOT_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    in_memory=False,
)

def wire(import_path: str):
    """Import a module and call its register(app) if present."""
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
    # ── Core portal: keep this the ONLY /start handler ───────────────────────────
    wire("dm_foolproof")

    # ── Panels wired through dm_foolproof (no additional /start handlers) ───────
    wire("handlers.help_panel")        # Help: Buyer Rules / Requirements / Game Rules
    wire("handlers.contact_admins")    # Contact Roni/Ruby, Suggestions, Anonymous

    # ── DM-ready lifecycle extras ────────────────────────────────────────────────
    wire("handlers.dmready_cleanup")   # Auto-remove DM-ready on leave/kick/ban

    # ── Menus (uses data/menus.json; keep your existing creator if you use it) ──
    wire("handlers.menu")              # optional viewer if you have it
    wire("handlers.createmenu")        # command to save/update menus

    # ── Your existing feature stack (must NOT register /start again) ────────────
    wire("handlers.dmnow")             # deep-link helper (no /start, safe)
    wire("handlers.dm_admin")
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.hi")
    wire("handlers.warmup")
    wire("handlers.health")
    wire("handlers.welcome")
    wire("handlers.bloop")
    wire("handlers.whoami")

    log.info("🚀 SuccuBot starting…")
    app.run()
