# main.py
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode

# -----------------------------
# Env & logging
# -----------------------------
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Missing API_ID / API_HASH / BOT_TOKEN in environment")

# -----------------------------
# Pyrogram client
# -----------------------------
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,  # <-- Pyrogram 2 requires the enum, not "html"
    in_memory=True,
)


# -----------------------------
# Handler wiring
# -----------------------------
def _try_import_and_register(module_name: str):
    """Import a module that has a `register(app)` function and call it."""
    try:
        mod = __import__(module_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("wired: %s", module_name)
        else:
            log.warning("%s has no register()", module_name)
    except Exception as e:
        log.error("Failed to wire %s: %s", module_name, e)


def wire_handlers():
    log.info("✅ Booting SuccuBot")

    # Root-level extras (keep dm_foolproof in project root)
    _try_import_and_register("dm_foolproof")

    # Handlers folder (only those present in your repo)
    handlers = [
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

    for name in handlers:
        _try_import_and_register(name)

    log.info("Handlers wired.")


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    wire_handlers()

    @app.on_client_started
    async def _on_started(client: Client):
        me = await client.get_me()
        log.info("Bot started as @%s (%s)", me.username, me.id)

    app.run()
