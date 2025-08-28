# main.py — SuccuBot bootstrap (explicit wiring, no Pyrogram plugin root)
import os
import asyncio
import signal
import logging
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("SuccuBot")

# ---------- Credentials ----------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH, BOT_TOKEN must be set in .env")

# ---------- Client (no plugins=root) ----------
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------- Wiring helper ----------
def wire(import_path: str):
    try:
        mod = __import__(import_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info(f"✅ Wired: {import_path}")
        else:
            log.warning(f"⚠️ No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

def wire_all():
    # Core portal + menus
    wire("dm_foolproof")
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # DM helpers / admin DM-ready tools
    wire("handlers.dmnow")             # <-- THIS FILE
    wire("handlers.dm_admin")          # (your existing deep-link utility, if still used elsewhere)
    wire("handlers.dm_ready_admin")    # /dmreadylist, remove/clear/debug

    # Requirements / reminders
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")

    # Flyers & scheduling
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")

    # Moderation / federation / utilities
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
    wire("handlers.whoami")  # optional: only if present

# ---------- Graceful shutdown ----------
_shutdown_called = False

def _graceful_stop(*_):
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True
    log.info("🛑 Stop signal received. Shutting down gracefully...")

    # stop APScheduler jobs if present
    try:
        from handlers.flyer_scheduler import scheduler as flyer_sched
        flyer_sched.shutdown(wait=False)
    except Exception:
        pass
    try:
        from handlers.schedulemsg import scheduler as msg_sched
        msg_sched.shutdown(wait=False)
    except Exception:
        pass

    # stop pyrogram
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(app.stop())
    except Exception:
        pass

signal.signal(signal.SIGTERM, _graceful_stop)
signal.signal(signal.SIGINT, _graceful_stop)

# ---------- Run ----------
if __name__ == "__main__":
    wire_all()
    log.info("🚀 SuccuBot starting…")
    app.run()
