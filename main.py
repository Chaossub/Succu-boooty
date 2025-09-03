# main.py
import os, logging, sys
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("SuccuBot")

API_ID   = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN= os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "succubot")

app = Client(
    BOT_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",          # store session files in root
    in_memory=False       # persist session
)

def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        mod.register(app)
        log.info("✅ Wired: %s", path)
    except Exception as e:
        log.exception("❌ Failed to wire %s: %s", path, e)

if __name__ == "__main__":
    # SINGLE /start handler
    wire("dm_foolproof")

    # Panels (Menus / Contact Admins / Help)
    wire("handlers.panels")

    # Menu commands (/addmenu, /menu, etc.)
    wire("handlers.menu")

    # Admin tools around DM-ready + deep link
    wire("handlers.dm_admin")
    wire("handlers.dmnow")
    wire("handlers.dmready_cleanup")

    # Everything else (none of these should register /start)
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
    wire("handlers.bloop")
    wire("handlers.whoami")

    log.info("🚀 SuccuBot starting…")
    app.run()
