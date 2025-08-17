# main.py — Pyrogram main thread; FastAPI health server in background.
# Wires the root-level dm_foolproof.py and every handlers/*.py that exposes register(app).

import logging, os, importlib, pkgutil, threading
from pyrogram import Client
from fastapi import FastAPI
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

bot = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def _wire_root_dm():
    """Load the root-level dm_foolproof.py (owns /start)."""
    try:
        from dm_foolproof import register as register_dm
        register_dm(bot)
        log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed wiring dm_foolproof: %s", e)

def _wire_handlers_pkg():
    """Import every handlers.* module and call register(app) if present."""
    try:
        import handlers
    except Exception as e:
        log.warning("No handlers package: %s", e)
        return
    for modinfo in pkgutil.iter_modules(handlers.__path__, handlers.__name__ + "."):
        name = modinfo.name
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, "register"):
                mod.register(bot)
                log.info("wired: %s", name)
        except Exception as e:
            log.exception("Failed import: %s (%s)", name, e)

# --- tiny FastAPI for uptime/health ---
api = FastAPI()
@api.get("/")
async def root():
    return {"ok": True, "bot": "SuccuBot"}

def _run_web():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(api, host="0.0.0.0", port=port, log_level="info")

def main():
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_root_dm()        # <- /start lives in dm_foolproof.py ONLY
    _wire_handlers_pkg()   # <- dmnow and others
    threading.Thread(target=_run_web, daemon=True).start()
    bot.run()

if __name__ == "__main__":
    main()
