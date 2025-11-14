# main.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

# ────────────── BOT INIT ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

def _try_register(module_path: str, name: str | None = None):
    mod_name = f"handlers.{module_path}"
    label = name or module_path
    try:
        mod = __import__(mod_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Registered %s", mod_name)
        else:
            log.warning("%s has no register()", mod_name)
    except Exception as e:
        log.warning("Skipping %s (import/register failed): %s", mod_name, e)

def main():
    log.info("💋 Starting SuccuBot…")

    # Warm-up / optional
    _try_register("hi")                      # /hi (warm-up)

    # Core panels & menus (this contains /start; DON'T add another /start here)
    _try_register("panels")                  # Menus picker + home

    # Contact Admins & DM helpers
    _try_register("contact_admins")          # contact_admins:open + anon flow
    _try_register("dm_admin")
    _try_register("dm_ready")
    _try_register("dm_ready_admin")

    # Help panel (buttons -> env text)
    _try_register("help_panel")              # help:open + pages

    # Menus persistence/creation
    _try_register("menu")                    # (mongo or json)
    _try_register("createmenu")

    # Moderation / warnings
    _try_register("moderation")
    _try_register("warnings")

    # Message scheduler
    _try_register("schedulemsg")

    # Flyers (ad-hoc send + CRUD)
    _try_register("flyer")                   # /addflyer /flyer /listflyers /deleteflyer /textflyer

    # Flyer scheduler (date/time -> post)
    _try_register("flyer_scheduler")
    try:
        # give scheduler the running loop so it can post from its thread
        from handlers import flyer_scheduler as _fs
        _fs.set_main_loop(app.loop)
        log.info("✅ Set main loop for flyer_scheduler")
    except Exception as e:
        log.warning("Could not set main loop for flyer_scheduler: %s", e)

    # 🔥 Stripe tip handler (one checkout per model)
    _try_register("stripe_tips")

    # -------- Central “Back to Main” handler (portal:home) --------
    @app.on_callback_query(filters.regex("^portal:home$"))
    async def _portal_home_cb(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ])
        try:
            await cq.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # Safety: if panels didn’t provide the “models_elsewhere:open” page, handle it here.
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def _models_elsewhere_cb(_, cq: CallbackQuery):
        text = FIND_MODELS_TEXT or "Nothing here yet 💕"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Main", callback_data="portal:home")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    app.run()

if __name__ == "__main__":
    main()

