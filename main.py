# main.py
import os
import logging
import importlib
from contextlib import suppress

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode

# Optional: MongoDB
with suppress(Exception):
    from pymongo import MongoClient  # only used if MONGO_URI provided

# ──────────────────────────────────────────────────────────────────────────────
# Env / logging
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
MONGO_URI = os.getenv("MONGO_URI")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise SystemExit("Missing API_ID / API_HASH / BOT_TOKEN in environment.")

# ──────────────────────────────────────────────────────────────────────────────
# App / DB
# ──────────────────────────────────────────────────────────────────────────────
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,  # ensures parse mode is valid for Pyrogram 2.x
    in_memory=True,
)

mongo_client = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        log.info("Mongo connected.")
    except Exception as e:
        log.error("Mongo connect failed: %s", e)

# ──────────────────────────────────────────────────────────────────────────────
# Wiring helpers
# ──────────────────────────────────────────────────────────────────────────────
def wire_module(mod_path: str):
    """
    Import `mod_path` and call its `wire(app, mongo_client, ...)` if present.
    Logs and continues if the module is missing or doesn't expose `wire`.
    """
    try:
        module = importlib.import_module(mod_path)
    except Exception as e:
        log.error("Failed to import %s: %s", mod_path, e)
        return

    # Prefer a `wire(app, mongo_client, **kwargs)` function
    if hasattr(module, "wire"):
        try:
            # Some modules may only accept (app) — be flexible.
            with suppress(TypeError):
                module.wire(app, mongo_client, owner_id=OWNER_ID)
                log.info("wired: %s", mod_path)
                return
            with suppress(TypeError):
                module.wire(app, mongo_client)
                log.info("wired: %s", mod_path)
                return
            # Last resort: just pass app
            module.wire(app)
            log.info("wired: %s", mod_path)
            return
        except Exception as e:
            log.error("Failed to wire %s: %s", mod_path, e)
            return

    # Fallbacks some projects use
    for fname in ("register", "setup", "init"):
        if hasattr(module, fname):
            try:
                getattr(module, fname)(app)
                log.info("wired (via %s): %s", fname, mod_path)
                return
            except Exception as e:
                log.error("Failed to %s %s: %s", fname, mod_path, e)
                return

    log.warning("No wire/register/setup in %s (skipped).", mod_path)

# ──────────────────────────────────────────────────────────────────────────────
# Wire core modules (order matters: dm_foolproof first so it seeds shared env)
# ──────────────────────────────────────────────────────────────────────────────
log.info("✅ Booting SuccuBot")

# Your two updated modules:
wire_module("dm_foolproof")
wire_module("handlers.menu")

# If you have other handler packages, we’ll try to wire them too (optional).
# These calls won’t crash the bot if a module is missing — they’ll just log.
optional_handlers = [
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
for mod in optional_handlers:
    wire_module(mod)

log.info("Handlers wired.")

# ──────────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run()

