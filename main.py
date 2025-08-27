# main.py
import logging
import os
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set.")

app = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, plugins=None)

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

def wire_all_handlers():
    # The ONLY /start portal:
    wire("dm_foolproof")

    # UI + panels + features
    wire("handlers.menu")
    wire("handlers.createmenu")
    wire("handlers.contact_admins")
    wire("handlers.help_panel")

    # Ops
    wire("handlers.enforce_requirements")
    wire("handlers.test_send")

    # Admin utilities
    wire("handlers.bloop")
    wire("handlers.whoami")

    # ❌ DO NOT wire the old portal; it would duplicate /start
    # wire("handlers.dm_portal")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()
