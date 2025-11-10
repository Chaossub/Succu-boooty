import os
import logging
import importlib
from pyrogram import Client
from pyrogram.enums import ParseMode

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("main")

API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing one or more required env vars: API_ID, API_HASH, BOT_TOKEN")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN,
)

def _register(module_path: str):
    try:
        mod = importlib.import_module(module_path)
    except Exception as e:
        log.warning("Skipping %s (import failed): %s", module_path, e)
        return
    reg = getattr(mod, "register", None)
    if callable(reg):
        try:
            reg(app)
            log.info("✅ Registered %s", module_path)
        except Exception as e:
            log.exception("Error registering %s: %s", module_path, e)
    else:
        log.warning("Skipping %s (no register(app))", module_path)

def main():
    print("💋 Starting SuccuBot…")

    targets = [
        "handlers.hi",             # /start with Menus button (opens /menus)
        "handlers.help",           # /help (if present)
        "handlers.moderation",
        "handlers.warnings",
        "handlers.schedulemsg",
        "handlers.panels",         # your flyers/panels (keeps its /menu if you use it)
        "handlers.menu",           # menus browser on /menus (no conflict with panels)
        "handlers.createmenu",     # /createmenu <Name> <text…>
        "handlers.dm_admin",
        "handlers.dm_ready",
        "handlers.dm_ready_admin",
        "handlers.menu_debug",     # /menus_status
    ]
    for m in targets:
        _register(m)

    print("✅ Handlers loaded. Running bot…\n")
    app.run()
    print("❌ Bot stopped.")

if __name__ == "__main__":
    main()
