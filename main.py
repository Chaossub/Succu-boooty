# main.py — single /start lives in dm_foolproof.py only.

import os, logging, sys
from pyrogram import Client, idle

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN= os.getenv("BOT_TOKEN", "")

app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, plugins=None)

def wire(import_path: str, label: str):
    try:
        mod = __import__(import_path, fromlist=["register"])
        mod.register(app)
        log.info("✅ Wired: %s", label)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", label, e, exc_info=True)

if __name__ == "__main__":
    # Order matters: dm_foolproof presents the first screen & handles /start
    wire("dm_foolproof", "dm_foolproof")
    wire("handlers.menu", "handlers.menu")
    wire("handlers.createmenu", "handlers.createmenu")
    wire("handlers.contact_admins", "handlers.contact_admins")
    wire("handlers.help_panel", "handlers.help_panel")

    # your other handlers…
    wire("handlers.enforce_requirements", "handlers.enforce_requirements")
    wire("handlers.req_handlers", "handlers.req_handlers")
    wire("handlers.test_send", "handlers.test_send")
    wire("handlers.dmnow", "handlers.dmnow")
    wire("handlers.dm_admin", "handlers.dm_admin")
    wire("handlers.flyer", "handlers.flyer")
    wire("handlers.flyer_scheduler", "handlers.flyer_scheduler")
    wire("handlers.schedulemsg", "handlers.schedulemsg")
    wire("handlers.moderation", "handlers.moderation")
    wire("handlers.warnings", "handlers.warnings")
    wire("handlers.federation", "handlers.federation")
    wire("handlers.summon", "handlers.summon")
    wire("handlers.xp", "handlers.xp")
    wire("handlers.fun", "handlers.fun")
    wire("handlers.hi", "handlers.hi")
    wire("handlers.warmup", "handlers.warmup")
    wire("handlers.health", "handlers.health")
    wire("handlers.welcome", "handlers.welcome")
    wire("handlers.bloop", "handlers.bloop")
    wire("handlers.whoami", "handlers.whoami")

    log.info("🚀 SuccuBot starting…")
    app.start()
    idle()
    app.stop()
