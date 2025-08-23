import os
import logging
from importlib import import_module
from typing import List
from pyrogram import Client

# ---------- logging ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")
log.info("✅ Booting SuccuBot")

# ---------- env ----------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not (API_ID and API_HASH and BOT_TOKEN):
    log.error("Missing API_ID / API_HASH / BOT_TOKEN in environment.")
    raise SystemExit(1)

# Use in-memory session so ephemeral hosts don’t try to write files
app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=".", in_memory=True)

# ---------- wiring ----------
def _wire(mod_path: str, note: str = "") -> bool:
    try:
        m = import_module(mod_path)
        if hasattr(m, "register"):
            m.register(app)
        log.info("wired: %s%s", mod_path, f" {note}".strip())
        return True
    except Exception as e:
        log.error("Failed to wire %s: %s", mod_path, e)
        return False

def wire_all():
    wired: List[str] = []
    # root module (NOT in handlers/)
    if _wire("dm_foolproof", note="(root)"):
        wired.append("dm_foolproof")

    # best-effort for the rest
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
        if _wire(mod):
            wired.append(mod)

    if wired:
        log.info("Handlers wired: %d module(s).", len(wired))
    else:
        log.warning("No handlers were wired!")

if __name__ == "__main__":
    wire_all()
    # NOTE: Pyrogram 2.x has no @app.on_client_started; just run.
    app.run()

