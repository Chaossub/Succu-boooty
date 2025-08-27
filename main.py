# main.py — clean wiring + graceful shutdown (no duplicate /start)
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
    raise RuntimeError("API_ID, API_HASH, BOT_TOKEN must be set")

# ---------- Client ----------
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None,  # we wire modules manually
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
    # The ONLY /start portal lives in dm_foolproof.py
    wire("dm_foolproof")

    # Legacy shim (safe — no /start), maps old callbacks to new handlers
    wire("handlers.dm_portal")

    # Core UI
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # Requirements / ops
    wire("handlers.enforce_requirements")
    wire("handlers.req_handlers")
    wire("handlers.test_send")

    # DM tools
    wire("handlers.dmnow")
    wire("handlers.dm_admin")

    # Flyers / schedulers
    wire("handlers.flyer")
    wire("handlers.flyer_scheduler")
    wire("handlers.schedulemsg")

    # Moderation + federation
    wire("handlers.moderation")
    wire("handlers.warnings")
    wire("handlers.federation")

    # Misc feature sets
    wire("handlers.summon")
    wire("handlers.xp")
    wire("handlers.fun")
    wire("handlers.hi")
    wire("handlers.warmup")
    wire("handlers.health")
    wire("handlers.welcome")

    # Admin utilities
    wire("handlers.bloop")
    wire("handlers.whoami")  # keep only if file exists

# ---------- Graceful shutdown ----------
_shutdown_called = False

def _graceful_stop(*_):
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True
    log.info("🛑 Stop signal received. Shutting down gracefully...")

    # Stop APScheduler instances if those modules expose a scheduler
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

    # Stop Pyrogram
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
