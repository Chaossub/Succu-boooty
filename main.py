# main.py
import os
import logging
from typing import List
from threading import Thread

from dotenv import load_dotenv
from pyrogram import Client
from fastapi import FastAPI
import uvicorn

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
log.info("👑 OWNER_ID = %s", OWNER_ID)

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=int(os.getenv("PYROGRAM_WORKERS", "16")),
    in_memory=False,
)

# IMPORTANT: Only one /start handler module: handlers.dm_ready
# (We are not wiring dm_foolproof to avoid duplicate /start.)
MODULES: List[str] = [
    "handlers.dm_ready",          # /start, mark DM-ready, notify owner
    "handlers.dm_ready_admin",    # /dmreadylist /dmreadyremove /dmreadyclear /dmreadydebug
    "handlers.dmready_watch",     # remove DM-ready on leave/kick/ban
    "handlers.dmready_cleanup",   # same goal (some clients only fire this)
    # Panels / menus / help
    "handlers.panels",
    "handlers.menu",
    "handlers.contact_admins",
    "handlers.help_panel",
    # Requirements & schedulers
    "handlers.enforce_requirements",
    "handlers.req_handlers",
    "handlers.flyer",
    "handlers.flyer_scheduler",
    "handlers.schedulemsg",
    # Moderation & misc
    "handlers.moderation",
    "handlers.warnings",
    "handlers.federation",
    "handlers.summon",
    "handlers.xp",
    "handlers.fun",
    "handlers.health",
    "handlers.bloop",
    "handlers.whoami",
]

def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", path)
        else:
            log.warning("ℹ️ No register() in %s", path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", path, e, exc_info=True)

# Small FastAPI to keep Render happy / for health checks
fast = FastAPI(title="SuccuBot Worker", version="1.0")
@fast.get("/")
def root():
    return {"ok": True}

def run_http():
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(fast, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)

    for m in MODULES:
        wire(m)

    Thread(target=run_http, daemon=True).start()
    log.info("🚀 SuccuBot starting…")
    app.run()
