import os
import logging
from pyrogram import Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

# --- Required creds ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("Please set API_ID, API_HASH, and BOT_TOKEN in environment variables.")

# --- Create client ---
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="."
)

def _wire_handlers():
    """
    Register handlers explicitly so only the intended /start (dm_foolproof) is active.
    Add/remove modules here as you grow, but keep /start only in dm_foolproof.
    """
    wired = 0

    # Import order is explicit; nothing here should register /start except dm_foolproof.
    from handlers import fun
    fun.register(app); log.info("wired: handlers.fun"); wired += 1

    from handlers import xp
    xp.register(app); log.info("wired: handlers.xp"); wired += 1

    from handlers import flyer
    flyer.register(app); log.info("wired: handlers.flyer"); wired += 1

    from handlers import menu
    menu.register(app); log.info("wired: handlers.menu"); wired += 1

    from handlers import warmup
    warmup.register(app); log.info("wired: handlers.warmup"); wired += 1

    from handlers import membership_watch
    membership_watch.register(app); log.info("wired: handlers.membership_watch"); wired += 1

    from handlers import exemptions
    exemptions.register(app); log.info("wired: handlers.exemptions"); wired += 1

    from handlers import help_panel
    help_panel.register(app); log.info("wired: handlers.help_panel"); wired += 1

    # ✅ Only file that should define /start
    from handlers import dm_foolproof
    dm_foolproof.register(app); log.info("wired: handlers.dm_foolproof (/start)"); wired += 1

    # The DM button helper (NO /start here)
    from handlers import dmnow
    dmnow.register(app); log.info("wired: handlers.dmnow (/dmnow)"); wired += 1

    log.info("Handlers wired: %s module(s) with register(app).", wired)

# Optional: tiny ping/health route if you run a FastAPI or uptime check elsewhere
@app.on_message()
async def _noop(_, __):
    return

if __name__ == "__main__":
    log.info("✅ Starting SuccuBot… (Pyrogram)")
    _wire_handlers()
    app.run()
