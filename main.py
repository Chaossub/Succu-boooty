# main.py
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
log.info("✅ Booting SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

def _wire(module_path: str, label: str = None):
    label = label or module_path
    try:
        m = __import__(module_path, fromlist=["register"])
        if hasattr(m, "register"):
            m.register(app)
            log.info("wired: %s", label)
        else:
            log.warning("Module missing register(): %s", module_path)
    except Exception as e:
        log.error("Failed to wire %s: %s", label, e)

# --- Handlers order ---
# 1) DM portal (+ DM-ready + contact admins/models + links + help)
_wire("dm_foolproof", "dm_foolproof")

# 2) Existing handlers in your repo (leave as-is)
for mod in [
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
    _wire(mod, mod)

log.info("Handlers wired.")

if __name__ == "__main__":
    app.run()
