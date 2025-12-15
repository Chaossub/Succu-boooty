# main.py
import os
import logging
from typing import Set
import importlib
import traceback

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


def _parse_id_list(val: str | None) -> Set[int]:
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


def _try_register(module_path: str, name: str | None = None):
    """
    Import handlers.<module_path> and call register(app).
    IMPORTANT: If it fails, we log a full traceback so nothing "dies silently".
    """
    mod_name = f"handlers.{module_path}"
    label = name or module_path
    try:
        mod = importlib.import_module(mod_name)
        reg = getattr(mod, "register", None)
        if callable(reg):
            reg(app)
            log.info("✅ Registered %s", mod_name)
        else:
            log.warning("⚠️ %s has no register(app)", mod_name)
    except Exception as e:
        log.error("❌ FAILED to import/register %s (%s): %s", mod_name, label, e)
        log.error("TRACE:\n%s", traceback.format_exc())


def main():
    log.info("💋 Starting SuccuBot…")
    log.info(
        "IDs loaded: OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
    )

    # Warm-up / optional
    _try_register("hi")  # /hi (warm-up)

    # Core panels & menus (this contains /start; DON'T add another /start here)
    _try_register("panels")  # Menus picker + home

    # Contact Admins & DM helpers
    _try_register("contact_admins")  # contact_admins:open + anon flow
    _try_register("dm_admin")
    _try_register("dm_ready")
    _try_register("dm_ready_admin")

    # IMPORTANT: keep these separate so /portal and /dmnow don’t collide.
    _try_register("dmnow")       # /dmnow → sanctuary mode DM button (ONLY)
    _try_register("dm_portal")   # legacy shim (keep, but dmnow is now its own handler)
    _try_register("portal_cmd")  # /portal → DM button (assistant)

    # Summon commands (/summonall, /summon)
    _try_register("summon")

    # ⭐ Roni personal assistant portal
    _try_register("roni_portal")      # core portal UI + text blocks
    _try_register("roni_portal_age")  # age verification + AV admin

    # ✅ NSFW availability + booking
    # These names MUST match your handler filenames:
    _try_register("nsfw_availability")         # nsfw_av:open + block/unblock
    _try_register("nsfw_text_session_booking") # nsfw_book:open booking flow

    # Help panel
    _try_register("help_panel")  # help:open + pages

    # Menus persistence/creation
    _try_register("menu")  # (mongo or json)
    _try_register("createmenu")

    # Moderation / warnings
    _try_register("moderation")
    _try_register("warnings")

    # Message scheduler
    _try_register("schedulemsg")

    # Flyers
    _try_register("flyer")  # /addflyer /flyer /listflyers /deleteflyer /textflyer
    _try_register("flyer_scheduler")

    # ⭐ Requirements panel
    _try_register("requirements_panel")

    # 🔻 Give both schedulers the running loop so they can post from their threads
    try:
        from handlers import flyer_scheduler as _fs
        _fs.set_main_loop(app.loop)
        log.info("✅ Set main loop for flyer_scheduler")
    except Exception as e:
        log.warning("Could not set main loop for flyer_scheduler: %s", e)

    try:
        from handlers import schedulemsg as _sm
        _sm.set_main_loop(app.loop)
        log.info("✅ Set main loop for schedulemsg")
    except Exception as e:
        log.warning("Could not set main loop for schedulemsg: %s", e)

    # Safety: if panels didn’t provide the “models_elsewhere:open” page, handle it here.
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def _models_elsewhere_cb(_, cq: CallbackQuery):
        text = FIND_MODELS_TEXT or "Nothing here yet 💕"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="panels:root")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    app.run()


if __name__ == "__main__":
    main()
