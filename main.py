# main.py — discover handlers/* and also wire root-level dm_foolproof.py
import os
import logging
import pkgutil
import importlib
from pyrogram import Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("Please set API_ID, API_HASH, BOT_TOKEN in env.")

app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir=".")

def _wire_handlers_package() -> None:
    wired = 0

    # 1) Try to wire the root-level dm_foolproof.py (this contains /start)
    try:
        spec = importlib.util.find_spec("dm_foolproof")
        if spec is not None:
            mod = importlib.import_module("dm_foolproof")
            if hasattr(mod, "register"):
                mod.register(app)
                wired += 1
                log.info("wired: dm_foolproof (root)")
            else:
                log.warning("skip: dm_foolproof (no register(app))")
        else:
            log.warning("skip: dm_foolproof (not found at repo root)")
    except Exception as e:
        log.exception("Failed import: dm_foolproof (%s)", e)

    # 2) Auto-discover handlers/*
    try:
        pkg = importlib.import_module("handlers")
        pkg_path = pkg.__path__
    except Exception as e:
        log.warning("No handlers package found (handlers/). (%s)", e)
        pkg_path = []

    for m in pkgutil.iter_modules(pkg_path):
        name = m.name
        modname = f"handlers.{name}"
        try:
            mod = importlib.import_module(modname)
            if hasattr(mod, "register"):
                mod.register(app)
                wired += 1
                log.info("wired: %s", modname)
            else:
                log.info("skip: %s (no register(app))", modname)
        except Exception as e:
            log.exception("Failed import: %s (%s)", modname, e)

    log.info("Handlers wired: %s module(s) with register(app).", wired)

@app.on_message()
async def _noop(_, __):
    return  # health/no-op

if __name__ == "__main__":
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_handlers_package()
    app.run()
