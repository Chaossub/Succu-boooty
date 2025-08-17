# main.py — auto-discover handlers/*
import os, logging, pkgutil, importlib
from pyrogram import Client

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("SuccuBot")

API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN= os.getenv("BOT_TOKEN", "")
if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("Please set API_ID, API_HASH, BOT_TOKEN in env.")

app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=".")

def _wire_handlers_package():
    """Import handlers.* and call register(app) if present."""
    wired = 0
    try:
        import handlers  # must exist and contain __init__.py
    except Exception as e:
        log.error("No 'handlers' package: %s", e)
        return

    for modinfo in pkgutil.iter_modules(handlers.__path__, prefix="handlers."):
        modname = modinfo.name
        try:
            mod = importlib.import_module(modname)
            reg = getattr(mod, "register", None)
            if callable(reg):
                reg(app)
                log.info("wired: %s", modname)
                wired += 1
            else:
                log.info("skip: %s (no register(app))", modname)
        except Exception as e:
            log.exception("Failed import: %s (%s)", modname, e)
    log.info("Handlers wired: %s module(s) with register(app).", wired)

@app.on_message()
async def _noop(_, __):  # health/no-op
    return

if __name__ == "__main__":
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_handlers_package()
    app.run()
