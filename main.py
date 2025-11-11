# main.py
import os
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# ────────────── LOGGING ──────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

# ────────────── BOT INIT ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN
)

# ────────────── SAFE IMPORT/REGISTER ──────────────
def _try_register(module_path: str, name: str | None = None):
    """
    Import handlers.<module_path> and call register(app) if present.
    Returns the imported module (or None) so we can call extra setup
    like set_main_loop for scheduler-based modules.
    """
    mod_name = f"handlers.{module_path}"
    label = name or module_path
    try:
        mod = __import__(mod_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Registered %s", mod_name)
        else:
            log.warning("%s has no register()", mod_name)
        return mod
    except Exception as e:
        log.warning("Skipping %s (import/register failed): %s", mod_name, e)
        return None

# ────────────── REGISTER HANDLERS ──────────────
def main():
    log.info("💋 Starting SuccuBot…")

    # Core / warm-up
    _try_register("hi")                     # /hi warm-up

    # Help panel (buttons: Buyer Requirements / Buyer Rules / Game Rules)
    _try_register("help_panel")             # provides help:open + subpages

    # Moderation & warnings
    _try_register("moderation")
    _try_register("warnings")

    # One-off scheduled messages (your existing)
    _try_register("schedulemsg")

    # Panels (model picker, book/tip, home buttons)
    _try_register("panels")

    # Menus (persistent store + create)
    _try_register("menu")                   # DB wiring log + readiness
    _try_register("createmenu")             # /createmenu <model> <text…>

    # DM helpers
    _try_register("dm_admin")
    _try_register("dm_ready")
    _try_register("dm_ready_admin")

    # Contact Admins
    _try_register("contact_admins")

    # Flyers (CRUD/manual) + Scheduler (timed posting)
    _try_register("flyer")                  # your handlers/flyer.py
    fs = _try_register("flyer_scheduler")   # your handlers/flyer_scheduler.py

    # Hand the running asyncio loop to flyer_scheduler so APScheduler
    # can safely dispatch coroutines (post_flyer) from its thread.
    try:
        if fs and hasattr(fs, "set_main_loop"):
            loop = asyncio.get_event_loop()
            fs.set_main_loop(loop)
            log.info("🧭 flyer_scheduler: main loop handed off")
    except Exception as e:
        log.warning("Could not hand off loop to flyer_scheduler: %s", e)

    # ────────────── MAIN MENU (portal:home) ──────────────
    @app.on_callback_query(filters.regex("^portal:home$"))
    async def _portal_home_cb(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
                [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
                [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
                [InlineKeyboardButton("❓ Help", callback_data="help:open")],
            ]
        )
        try:
            await cq.message.edit_text(
                "🔥 **Welcome back to SuccuBot**\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # ────────────── /start FALLBACK ──────────────
    @app.on_message(filters.command("start"))
    async def _start_fallback(_, m: Message):
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
                [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
                [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
                [InlineKeyboardButton("❓ Help", callback_data="help:open")],
            ]
        )
        await m.reply_text(
            "🔥 **Welcome to SuccuBot**\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    app.run()

# ────────────── ENTRY ──────────────
if __name__ == "__main__":
    main()
