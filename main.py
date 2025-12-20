# main.py (updated)
import os
import logging
from typing import Set, Optional

from pyrogram import Client
from pyrogram.enums import ParseMode

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

def _parse_id_list(val: Optional[str]) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning("main: bad ID in list: %r", part)
    return out

SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS"))

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

def _try_register(module_path: str, *, critical: bool = False):
    mod_name = f"handlers.{module_path}"
    try:
        mod = __import__(mod_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Registered %s", mod_name)
        else:
            msg = f"{mod_name} has no register()"
            if critical:
                raise RuntimeError(msg)
            log.warning(msg)
    except ModuleNotFoundError:
        log.warning("⚠️ Skipping missing module %s", mod_name)
        if critical:
            raise
    except Exception:
        log.exception("❌ FAILED registering %s", mod_name)
        if critical:
            raise

def main():
    log.info("💋 Starting SuccuBot…")
    log.info("IDs loaded: OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s", OWNER_ID, SUPER_ADMINS, MODELS)

    _try_register("health")
    _try_register("panels", critical=True)

    _try_register("contact_admins")
    _try_register("dm_admin")

    _try_register("dm_ready", critical=True)
    _try_register("dmready_bridge", critical=True)
    _try_register("dm_ready_admin")
    _try_register("dmnow", critical=True)
    _try_register("portal_cmd", critical=True)

    _try_register("summon")

    _try_register("roni_portal", critical=True)
    _try_register("roni_portal_age", critical=True)

    # ✅ Availability + Booking (REPLACE these two handler files with the fixed versions)
    _try_register("nsfw_text_session_availability", critical=True)
    _try_register("nsfw_text_session_booking", critical=True)

    _try_register("help_panel", critical=True)
    _try_register("menu")
    _try_register("createmenu")

    _try_register("moderation")
    _try_register("warnings")
    _try_register("fun")

    _try_register("schedulemsg")

    _try_register("flyer")
    _try_register("flyer_scheduler")

    _try_register("requirements_panel", critical=True)

    # NEW: push-button kicking UI for requirements
    _try_register("kick_requirements", critical=True)

    # Pass loop into schedulers if present
    try:
        from handlers import flyer_scheduler as _fs
        _fs.set_main_loop(app.loop)
        log.info("✅ Set main loop for flyer_scheduler")
    except Exception:
        log.exception("Could not set main loop for flyer_scheduler")

    try:
        from handlers import schedulemsg as _sm
        _sm.set_main_loop(app.loop)
        log.info("✅ Set main loop for schedulemsg")
    except Exception:
        log.exception("Could not set main loop for schedulemsg")

    app.run()

if __name__ == "__main__":
    main()
