import os
import importlib
import pkgutil
import logging
import asyncio
from dotenv import load_dotenv
from pyrogram import Client

log = logging.getLogger("SuccuBot")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

load_dotenv()

API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".",
    plugins=None,  # we wire manually
)

def _wire_root():
    # dm_foolproof is in the project root (not in handlers)
    try:
        import dm_foolproof
        dm_foolproof.register(app)
        log.info("wired: dm_foolproof (root)")
    except Exception as e:
        log.exception("Failed to wire dm_foolproof: %s", e)

def _wire_handlers_package():
    try:
        import handlers
    except ImportError:
        log.warning("No handlers package found; skipping.")
        return

    for modinfo in pkgutil.walk_packages(handlers.__path__, handlers.__name__ + "."):
        modname = modinfo.name
        # Skip any accidental duplicates of dm_foolproof
        if modname.endswith(".dm_foolproof") or modname.endswith(".foolproofdm") or modname.endswith(".dm_foolproof_start"):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            log.warning("skip: %s (import error: %s)", modname, e)
            continue
        if hasattr(mod, "register"):
            try:
                mod.register(app)
                log.info("wired: %s", modname)
            except Exception as e:
                log.exception("Failed wiring %s: %s", modname, e)

async def _who_am_i():
    async with app:
        me = await app.get_me()
        log.info("🤖 Running as @%s (id=%s)", me.username, me.id)

if __name__ == "__main__":
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_root()
    _wire_handlers_package()
    # Log which bot handle is live so you can DM the correct one
    asyncio.get_event_loop().run_until_complete(_who_am_i())
    app.run()

