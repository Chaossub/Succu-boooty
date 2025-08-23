import os
import logging
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_NAME = os.getenv("SESSION_NAME", "SuccuBot")

app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def _wire(module_name: str, attr: str = "register"):
    try:
        mod = __import__(module_name, fromlist=[attr])
        getattr(mod, attr)(app)
        log.info("wired: %s", module_name)
    except Exception as e:
        log.warning("Module not found (skipped): %s (%s)", module_name, e)

def wire_all():
    log.info("✅ Starting SuccuBot with enhanced logging")
    # ---- DM portal lives in root as dm_foolproof ----
    _wire("dm_foolproof")

    # ---- core handlers (keep your existing ones) ----
    _wire("handlers.menu")
    _wire("handlers.help_panel")
    _wire("handlers.help_cmd")
    _wire("handlers.req_handlers")
    _wire("handlers.enforce_requirements")
    _wire("handlers.exemptions")
    _wire("handlers.membership_watch")
    _wire("handlers.flyer")
    _wire("handlers.flyer_scheduler")
    _wire("handlers.schedulemsg")
    _wire("handlers.warmup")
    _wire("handlers.hi")
    _wire("handlers.fun")
    _wire("handlers.warnings")
    _wire("handlers.moderation")
    _wire("handlers.federation")
    _wire("handlers.summon")
    _wire("handlers.xp")
    _wire("handlers.dmnow")

    log.info("Handlers wired.")

if __name__ == "__main__":
    wire_all()
    app.run()
