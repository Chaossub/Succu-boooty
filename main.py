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

def wire(import_path: str):
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
    # The ONLY /start handler (prevents duplicates)
    wire("dm_foolproof")

    # Consolidated panel/UI router (Menus, Contact Admins, Help, Models Elsewhere)
    wire("handlers.panels")

    # Menus save/update command stays as-is
    wire("handlers.createmenu")

    # DM helper & admin tools (no /start here)
    wire("handlers.dmnow")
    wire("handlers.dm_admin")

    # Remove DM-ready when users leave/kicked/banned in Sanctuary groups
    wire("handlers.dmready_cleanup")

    # Your existing stack (must not register /start)
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
