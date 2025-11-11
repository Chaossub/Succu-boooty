# main.py
import os
import logging
import asyncio
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

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

def build_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ]
    )

# ────────────── REGISTER HANDLERS ──────────────
def main():
    log.info("💋 Starting SuccuBot…")

    # Core/simple
    _try_register("hi")
    _try_register("help")                   # optional

    # Moderation & warnings
    _try_register("moderation")
    _try_register("warnings")

    # Message scheduler (your other feature, not flyers)
    _try_register("schedulemsg")

    # Panels (menus picker, book/tip, home)
    _try_register("panels")

    # Menus persistence / creation
    _try_register("menu")
    _try_register("createmenu")

    # DM helpers
    _try_register("dm_admin")
    _try_register("dm_ready")
    _try_register("dm_ready_admin")

    # Contact Admins
    _try_register("contact_admins")

    # FLYERS: CRUD + posting
    _try_register("flyers")

    # FLYER SCHEDULER (schedule/cancel/list)
    _try_register("flyer_scheduler")

    # Back to Main (used by contact_admins)
    @app.on_callback_query(filters.regex("^portal:home$"))
    async def _portal_home_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "🔥 **Welcome back to SuccuBot**\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=build_home_kb(),
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # /start fallback (in case panels didn't define it)
    @app.on_message(filters.command("start"))
    async def _start_fallback(_, m: Message):
        await m.reply_text(
            "🔥 **Welcome to SuccuBot**\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=build_home_kb(),
            disable_web_page_preview=True,
        )

    # —— Start the bot explicitly so we can hand the running loop to the flyer scheduler ——
    app.start()
    try:
        # hand the REAL running loop to the scheduler module
        try:
            from handlers import flyer_scheduler as _fs
            _fs.set_main_loop(asyncio.get_running_loop())
            log.info("✅ Flyer scheduler received running loop")
        except Exception as e:
            log.warning("Could not set flyer scheduler loop: %s", e)

        idle()  # block here until Ctrl+C / stop
    finally:
        app.stop()

# ────────────── ENTRY ──────────────
if __name__ == "__main__":
    main()

