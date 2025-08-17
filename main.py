import os
import logging
import importlib
from pyrogram import Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("Please set API_ID, API_HASH, and BOT_TOKEN in env.")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="."
)

def _load_and_register(modname: str) -> bool:
    """Import handlers.<modname> and call register(app) if present."""
    fq = f"handlers.{modname}"
    try:
        mod = importlib.import_module(fq)
    except Exception as e:
        log.warning("skip: %s (import error: %s)", fq, e)
        return False
    if hasattr(mod, "register") and callable(mod.register):
        try:
            mod.register(app)
            log.info("wired: %s", fq)
            return True
        except Exception as e:
            log.exception("Failed register() in %s: %s", fq, e)
            return False
    else:
        log.warning("skip: %s (no register(app))", fq)
        return False

def _wire_handlers():
    """Explicit order. Keep /start ONLY in the foolproof DM module."""
    wired = 0

    for name in [
        "fun",
        "xp",
        "flyer",
        "menu",
        "warmup",
        "membership_watch",
        "exemptions",
        "help_panel",
    ]:
        wired += 1 if _load_and_register(name) else 0

    # ✅ Try multiple possible filenames for your foolproof DM /start module
    foolproof_candidates = ["dm_foolproof", "foolproofdm", "dm_foolproof_start"]
    fp_wired = False
    for cand in foolproof_candidates:
        if _load_and_register(cand):
            log.info("✅ /start is provided by: handlers.%s", cand)
            fp_wired = True
            wired += 1
            break
    if not fp_wired:
        log.error("❌ Could not find a handlers.dm_foolproof-style module for /start. "
                  "Ensure the file exists (e.g., handlers/dm_foolproof.py) and defines register(app).")

    # DM Now button helper (NO /start here)
    if _load_and_register("dmnow"):
        wired += 1

    log.info("Handlers wired: %d module(s) with register(app).", wired)

@app.on_message()
async def _noop(_, __):
    return

if __name__ == "__main__":
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_handlers()
    app.run()
