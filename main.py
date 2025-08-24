import logging
import os
from pyrogram import Client

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")
log.info("✅ Booting SuccuBot")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

def _wire(module_name: str, register_name: str = "register"):
    try:
        m = __import__(module_name, fromlist=[register_name])
        getattr(m, register_name)(app)
        log.info("wired: %s", module_name)
    except Exception as e:
        log.error("Failed to wire %s: %s", module_name, e)

# --- Wire modules ---
# dm_foolproof is in the project root (NOT under handlers)
_wire("dm_foolproof")

# Keep your other handlers wiring exactly as you have them today:
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
    _wire(mod)

log.info("Handlers wired.")

if __name__ == "__main__":
    # NOTE: Pyrogram 2.x does NOT have @app.on_client_started; we just run.
    app.run()
