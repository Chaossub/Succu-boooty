import os
import asyncio
import logging
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

# ---- Logging (shows in Render logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

API_ID = int(need("API_ID"))
API_HASH = need("API_HASH")
BOT_TOKEN = need("BOT_TOKEN")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# === Import and register handlers ===
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
    flyer_scheduler,
    warnings,
    warmup,
    hi,
    schedulemsg,
)
from handlers.req_handlers import wire_requirements_handlers
from dm_foolproof import register as register_dm_foolproof

# set event loop for schedulers BEFORE registering
event_loop = asyncio.get_event_loop()
flyer_scheduler.set_main_loop(event_loop)
schedulemsg.set_main_loop(event_loop)

# register all handlers
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
warnings.register(app)
flyer.register(app)
warmup.register(app)
hi.register(app)
schedulemsg.register(app)
flyer_scheduler.register(app)
wire_requirements_handlers(app)
register_dm_foolproof(app)

async def main():
    log.info("✅ Starting SuccuBot (background worker)…")
    await app.start()
    log.info("✅ SuccuBot is running and will idle…")
    try:
        while True:
            await asyncio.sleep(3600)  # keep the worker alive
    except asyncio.CancelledError:
        pass
    finally:
        log.info("🛑 Stopping SuccuBot…")
        await app.stop()
        log.info("🛑 SuccuBot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        log.exception("❌ Fatal error during startup")
        raise

