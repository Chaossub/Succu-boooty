import os
import logging
from typing import Set

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN= os.getenv("BOT_TOKEN", "")

# Optional (but strongly recommended)
OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

# ────────────── APP ──────────────
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ────────────── HANDLER LOADER ──────────────
REGISTERED: Set[str] = set()

def _try_register(module_name: str, critical: bool = False):
    """
    Import handlers.<module_name> and call register(app) if present.
    If critical=True, import errors will raise.
    """
    try:
        mod = __import__(f"handlers.{module_name}", fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            REGISTERED.add(module_name)
            log.info("✅ Registered: handlers.%s", module_name)
        else:
            log.warning("⚠️ handlers.%s has no register(app).", module_name)
    except Exception as e:
        if critical:
            raise
        log.error("❌ Failed to register handlers.%s: %s", module_name, e)

def _set_main_loop_for_scheduler():
    """
    Some schedulers need the main asyncio loop (if module exists).
    """
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        import handlers.flyer_scheduler as flyer_scheduler
        flyer_scheduler.MAIN_LOOP = loop
        log.info("✅ Set MAIN_LOOP for flyer_scheduler")
    except Exception as e:
        log.warning("⚠️ Could not set MAIN_LOOP for flyer_scheduler: %s", e)

# ────────────── BASIC COMMANDS ──────────────
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(_, msg):
    await msg.reply_text(
        "Hi! I’m alive ✅\n\nUse /help to see commands.",
        disable_web_page_preview=True
    )

@app.on_message(filters.private & filters.command("help"))
async def help_cmd(_, msg):
    await msg.reply_text(
        "<b>SuccuBot Help</b>\n\n"
        "• /start\n"
        "• /help\n\n"
        "Other features are available via the portal/panels.",
        disable_web_page_preview=True
    )

# ────────────── MAIN ──────────────
def main():
    log.info("Booting SuccuBot… OWNER_ID=%s", OWNER_ID)

    # If you have schedulers that need the main loop:
    _set_main_loop_for_scheduler()

    # Core panels / portal
    _try_register("roni_portal", critical=True)

    # DM-ready + requirements
    _try_register("dm_ready", critical=True)          # DM-ready tracking + panel compatibility fix
    _try_register("dmready_bridge")                   # mirrors dm_ready -> requirements_members (fixes DM-ready list)

    # Requirements panel
    _try_register("requirements_panel", critical=False)

    # NSFW scheduling (availability + booking)
    _try_register("nsfw_text_session_availability", critical=False)
    _try_register("nsfw_text_session_booking", critical=False)

    # Other optional handlers (safe load)
    _try_register("flyers", critical=False)
    _try_register("flyer_scheduler", critical=False)
    _try_register("schedulemsg", critical=False)

    log.info("Registered handlers: %s", ", ".join(sorted(REGISTERED)) if REGISTERED else "(none)")
    app.run()

if __name__ == "__main__":
    main()
