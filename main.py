# main.py
import os
import logging
from typing import Set, Optional

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

# Owner id (used by a few handlers)
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

# ────────────── BOT INIT ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)


def _try_register(module_path: str, *, critical: bool = False):
    """
    Imports handlers.<module_path> and calls register(app).
    If critical=True, crash on failure so we don't "silently" lose buttons.
    """
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
    except Exception:
        # FULL traceback so you can see exactly what broke
        log.exception("❌ FAILED registering %s", mod_name)
        if critical:
            raise


def main():
    log.info("💋 Starting SuccuBot…")
    log.info(
        "IDs loaded: OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
    )

    # Warm-up / optional
    _try_register("hi")

    # Core panels & menus (contains /start; DON'T add another /start elsewhere)
    _try_register("panels", critical=True)

    # Contact Admins & DM helpers
    _try_register("contact_admins")
    _try_register("dm_admin")
    _try_register("dm_ready", critical=True)          # DM-ready tracking + panel compatibility fix
    _try_register("dm_ready_admin")
    _try_register("dmnow", critical=True)             # /dmnow = sanctuary mode (KEEP WORKING)
    _try_register("portal_cmd", critical=True)        # /portal = Roni assistant DM button (DO NOT CONFLICT)

    # Summon commands
    _try_register("summon")

    # ⭐ Roni assistant
    _try_register("roni_portal", critical=True)
    _try_register("roni_portal_age", critical=True)

    # ✅ NSFW booking + availability
    _try_register("nsfw_text_session_availability", critical=True)
    _try_register("nsfw_text_session_booking", critical=True)

    # Help panel
    _try_register("help_panel", critical=True)

    # Menus persistence/creation
    _try_register("menu")
    _try_register("createmenu")

    # Moderation / warnings
    _try_register("moderation")
    _try_register("warnings")

    # Message scheduler
    _try_register("schedulemsg")

    # Flyers
    _try_register("flyer")
    _try_register("flyer_scheduler")

    # ⭐ Requirements panel
    _try_register("requirements_panel", critical=True)

    # Give schedulers the running loop so they can post from threads
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

    # Safety: if panels didn’t provide the “models_elsewhere:open” page, handle it here.
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def _models_elsewhere_cb(_, cq: CallbackQuery):
        text = FIND_MODELS_TEXT or "Nothing here yet 💕"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="panels:root")]]
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    app.run()


if __name__ == "__main__":
    main()
