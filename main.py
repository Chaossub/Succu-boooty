# main.py (SAFE BOOT version for Render crash-loops)
# - Never hard-crashes due to a single bad handler import/register.
# - Logs full exceptions so you can see exactly which handler is failing.
# - Keeps the bot running as long as core credentials are present.

import os
import logging
from typing import Set, Optional

from pyrogram import Client
from pyrogram.enums import ParseMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

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

def _try_register(module_path: str):
    """
    Import handlers.<module_path> and call register(app) if present.
    NEVER raises — logs exceptions instead, so one broken handler won't crash the worker.
    """
    mod_name = f"handlers.{module_path}"
    try:
        mod = __import__(mod_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Registered %s", mod_name)
        else:
            log.warning("⚠️ %s has no register()", mod_name)
    except Exception as e:
        log.exception("❌ FAILED registering %s: %s", mod_name, e)

def main():
    log.info("💋 Starting SuccuBot (safe boot)…")
    try:
        import sys
        log.info("Python: %s", sys.version.replace("\n", " "))
    except Exception:
        pass

    log.info("IDs loaded: OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s", OWNER_ID, SUPER_ADMINS, MODELS)

    # Register EVERYTHING non-fatally (prevents Render restart-loop)
    _try_register("health")
    _try_register("panels")

    # Warmup /hi
    _try_register("hi")

    _try_register("contact_admins")
    _try_register("dm_admin")

    _try_register("dm_ready")
    _try_register("dmready_bridge")
    _try_register("dm_ready_admin")
    _try_register("dmnow")
    _try_register("portal_cmd")

    _try_register("summon")

    _try_register("roni_portal")
    _try_register("roni_portal_age")

    _try_register("nsfw_text_session_availability")
    _try_register("nsfw_text_session_booking")

    _try_register("help_panel")
    _try_register("menu")
    _try_register("createmenu")

    _try_register("moderation")
    _try_register("warnings")
    _try_register("fun")

    _try_register("schedulemsg")

    _try_register("flyer")
    _try_register("flyer_scheduler")

    _try_register("requirements_panel")
    _try_register("kick_requirements")

    # Pass loop into schedulers if present (non-fatal)
    try:
        from handlers import flyer_scheduler as _fs
        if hasattr(_fs, "set_main_loop"):
            _fs.set_main_loop(app.loop)
            log.info("✅ Set main loop for flyer_scheduler")
    except Exception:
        log.exception("Could not set main loop for flyer_scheduler")

    try:
        from handlers import schedulemsg as _sm
        if hasattr(_sm, "set_main_loop"):
            _sm.set_main_loop(app.loop)
            log.info("✅ Set main loop for schedulemsg")
    except Exception:
        log.exception("Could not set main loop for schedulemsg")

    # Run the bot
    try:
        app.run()
    except Exception as e:
        log.exception("❌ Bot crashed during app.run(): %s", e)
        raise

if __name__ == "__main__":
    main()
