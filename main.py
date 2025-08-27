# main.py
import os
import logging
from importlib import import_module

from dotenv import load_dotenv
from pyrogram import Client

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("SuccuBot")

# ── Env ───────────────────────────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not (API_ID and API_HASH and BOT_TOKEN):
    logger.warning("API_ID / API_HASH / BOT_TOKEN are not fully set in the environment")

# ── Pyrogram Client ───────────────────────────────────────────────────────────
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=os.getcwd(),
    in_memory=True,  # keeps sessions ephemeral on hosts like Render/Heroku
)

# ── Helper to wire modules safely ─────────────────────────────────────────────
def wire(module_path: str, title: str | None = None) -> None:
    """
    Import `<module_path>`, call its `register(app)` if present,
    and log either 'wired:' or a clear error with traceback.
    """
    display = title or module_path
    try:
        mod = import_module(module_path)
    except Exception as e:
        logger.error("Failed to import %s: %s", display, e, exc_info=True)
        return

    register = getattr(mod, "register", None)
    if not callable(register):
        logger.error("Failed to wire %s: no register(app) found", display)
        return

    try:
        register(app)
        logger.info("wired: %s", display)
    except Exception as e:
        logger.error("Failed to wire %s: %s", display, e, exc_info=True)


# ── Wire all handlers here ────────────────────────────────────────────────────
def wire_all_handlers() -> None:
    """
    Keep this list in the exact order you want handlers to be registered.
    Nothing here uses filters.edited or on_client_started.
    """
    # root-level helper (per your note: dm_foolproof is at the project root)
    wire("dm_foolproof", "dm_foolproof")

    # primary UI / commands
    wire("handlers.menu", "handlers.menu")
    wire("handlers.help_panel", "handlers.help_panel")
    wire("handlers.help_cmd", "handlers.help_cmd")
    wire("handlers.req_handlers", "handlers.req_handlers")

    # policy/automation layers
    wire("handlers.enforce_requirements", "handlers.enforce_requirements")
    wire("handlers.exemptions", "handlers.exemptions")
    wire("handlers.membership_watch", "handlers.membership_watch")

    # scheduled / flyer systems
    wire("handlers.flyer", "handlers.flyer")
    # flyer_scheduler needs to import & schedule jobs on import/register
    wire("handlers.flyer_scheduler", "handlers.flyer_scheduler")

    # scheduled messages module
    wire("handlers.schedulemsg", "handlers.schedulemsg")

    # fun & misc UX
    wire("handlers.warmup", "handlers.warmup")
    wire("handlers.hi", "handlers.hi")
    wire("handlers.fun", "handlers.fun")
    wire("handlers.warnings", "handlers.warnings")
    wire("handlers.moderation", "handlers.moderation")
    wire("handlers.federation", "handlers.federation")
    wire("handlers.summon", "handlers.summon")
    wire("handlers.xp", "handlers.xp")
    wire("handlers.dmnow", "handlers.dmnow")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("✅ Booting SuccuBot")
    wire_all_handlers()

    # Start the bot (no @app.on_client_started, no idle() needed with run())
    app.run()

