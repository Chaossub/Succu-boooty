import os
import logging
from dotenv import load_dotenv
from pyrogram import Client

# --------------------------- env & logging ---------------------------
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    log.error("Missing API_ID/API_HASH/BOT_TOKEN.")
    raise SystemExit(1)

# --------------------------- app ---------------------------
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode="html",
    in_memory=True,
)

# --------------------------- dynamic wiring ---------------------------
def _wire_one(modname: str):
    try:
        m = __import__(modname, fromlist=["register"])
    except Exception as e:
        log.error("Failed to import %s: %s", modname, e)
        return
    try:
        if hasattr(m, "register"):
            m.register(app)
            log.info("wired: %s", modname)
        else:
            log.warning("%s has no register()", modname)
    except Exception as e:
        log.error("Failed to wire %s: %s", modname, e)

def wire_handlers():
    log.info("✅ Booting SuccuBot")
    modules = [
        # root module (NOT under handlers)
        "dm_foolproof",

        # your existing handlers (wire those that exist; missing are skipped gracefully)
        "handlers.menu",
        "handlers.help_panel",
        "handlers.help_cmd",
        "handlers.req_handlers",
        "handlers.enforce_requirements",
        "handlers.exemptions",
        "handlers.membership_watch",
        "handlers.flyer",
        "handlers.flyer_scheduler",
        "handlers.schedulemsg",
        "handlers.warmup",
        "handlers.hi",
        "handlers.fun",
        "handlers.warnings",
        "handlers.moderation",
        "handlers.federation",
        "handlers.summon",
        "handlers.xp",
        "handlers.dmnow",
    ]
    for name in modules:
        _wire_one(name)
    log.info("Handlers wired.")

# --------------------------- main ---------------------------
if __name__ == "__main__":
    wire_handlers()
    app.run()
