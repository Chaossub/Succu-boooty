# main.py
import os
import logging
import importlib
from pyrogram import Client
from pyrogram.enums import ParseMode

# ────────────── LOGGING ──────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("main")

# ────────────── ENVIRONMENT ──────────────
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing one or more required env vars: API_ID, API_HASH, BOT_TOKEN")

# ────────────── BOT CLIENT ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN,
)

# ────────────── HELPER: safe import/register ──────────────
def _register(module_path: str):
    """
    Import handlers.<name> and call register(app) if present.
    Gives clear logs if import fails or register(app) is missing.
    """
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
        log.warning("Skipping %s (no register(app) found)", module_path)

# ────────────── MAIN ──────────────
def main():
    print("💋 Starting SuccuBot…")

    # EXACT modules you asked to wire:
    targets = [
        # greetings / basic UX
        "handlers.hi",             # /start (if you keep it here) or /hi
        "handlers.help",           # /help (if you have a dedicated file)

        # moderation & warnings
        "handlers.moderation",     # /ban /kick /mute /unmute /warn … (your moderation suite)
        "handlers.warnings",       # /warns /resetwarns …

        # scheduling
        "handlers.schedulemsg",    # schedule message commands
        "handlers.panels",         # flyers / panels scheduler/manager

        # menus
        "handlers.menu",           # menu core (storage/plumbing)
        "handlers.createmenu",     # /createmenu (your create/update command)

        # DM tools
        "handlers.dm_admin",       # admin DM portal/commands
        "handlers.dm_ready",       # member readiness tracker
        "handlers.dm_ready_admin", # admin view/controls for readiness
    ]

    for m in targets:
        _register(m)

    print("✅ Handlers loaded. Running bot…\n")
    app.run()
    print("❌ Bot stopped.")

# ────────────── ENTRY POINT ──────────────
if __name__ == "__main__":
    main()
