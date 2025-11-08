# main.py — wires only the intended handlers and forces OWNER_ID
import os
import logging
from pyrogram import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

# Force owner id (you asked for this explicit override)
os.environ["OWNER_ID"] = "6964994611"

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH") or ""
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""

app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def wire(module_path: str):
    try:
        mod = __import__(module_path, fromlist=["register"])
        mod.register(app)
        log.info("✅ Wired: %s", module_path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", module_path, e)

if __name__ == "__main__":
    log.info("👑 OWNER_ID = %s", os.getenv("OWNER_ID"))
    # Minimal, de-duped wiring order
    wire("dm_foolproof")          # single /start and home keyboard
    wire("handlers.dm_ready")     # DM-ready tracker (Mongo)
    wire("handlers.panels")       # menus/help/contact/models
    wire("handlers.menu")         # model menus (Mongo)
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
    log.info("🚀 SuccuBot starting…")
    app.run()
