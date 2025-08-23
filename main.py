import os
import logging
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

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
        log.error("Failed to wire %s: %s", module_name, e)

def wire_all():
    log.info("✅ Booting SuccuBot")
    # Portal handler lives in REPO ROOT as dm_foolproof.py
    _wire("dm_foolproof")

    for m in [
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
    ]:
        _wire(m)
    log.info("Handlers wired.")

if __name__ == "__main__":
    wire_all()
    app.run()
