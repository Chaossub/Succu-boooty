# main.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID   = int(os.getenv("API_ID", "0"))
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
    parse_mode=ParseMode.HTML
)

def _try_register(module_path: str, name: str | None = None):
    mod_name = f"handlers.{module_path}"
    label = name or module_path
    try:
        module = __import__(mod_name, fromlist=["register"])
        if hasattr(module, "register"):
            module.register(app)
            log.info(f"Loaded handler: {label}")
        else:
            log.warning(f"No register() in handler: {label}")
    except Exception as e:
        log.exception(f"Error loading handler {label}: {e}")

# ────────────── LOAD HANDLERS ──────────────
def main():
    # Core panels & menus
    _try_register("panels")          # your main bot home menu
    _try_register("menu")            # existing
    _try_register("contact_admins")  # existing
    _try_register("payments")        # existing
    _try_register("book_handler")    # existing
    _try_register("models")          # existing
    _try_register("profile")         # existing
    _try_register("admin")           # existing handlers

    # ⭐ NEW — your Roni personal portal
    _try_register("roni_portal")

    # Any other handlers you already have remain untouched

    app.run()


if __name__ == "__main__":
    main()
