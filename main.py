# main.py
import os, logging
from threading import Thread
from typing import List

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

API_ID    = int(os.getenv("API_ID", "0") or "0")
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID  = int(os.getenv("OWNER_ID", "0") or "0")
log.info("👑 OWNER_ID = %s", OWNER_ID)

bot = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=int(os.getenv("PYROGRAM_WORKERS", "16")),
    in_memory=False,
)

# IMPORTANT:
#   Do NOT wire any other module that registers /start.
#   If a legacy module still does, remove/comment that handler there.
MODULES: List[str] = [
    "handlers.dm_ready",          # ONLY /start + /dmreadylist lives here
    "handlers.dmready_watch",     # leave/kick/ban cleanup
    "handlers.dmready_cleanup",   # extra coverage
    # The rest of your bot (must not define /start):
    "handlers.menu",
    "handlers.contact_admins",
    "handlers.help_panel",
    "handlers.enforce_requirements",
    "handlers.req_handlers",
    "handlers.flyer",
    "handlers.flyer_scheduler",
    "handlers.schedulemsg",
    "handlers.moderation",
    "handlers.warnings",
    "handlers.federation",
    "handlers.summon",
    "handlers.xp",
    "handlers.fun",
    "handlers.health",
    "handlers.bloop",
    "handlers.whoami",
    # DO NOT include dm_foolproof or any legacy /start module
]

def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(bot)
            log.info("✅ Wired: %s", path)
        else:
            log.warning("ℹ️ No register() in %s", path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", path, e, exc_info=True)

# Tiny health server
fast = FastAPI(title="SuccuBot Worker", version="1.0")
@fast.get("/")
def ok():
    return {"ok": True}

def run_http():
    uvicorn.run(fast, host="0.0.0.0", port=int(os.getenv("PORT", "10000")), log_level="info")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    for m in MODULES:
        wire(m)
    Thread(target=run_http, daemon=True).start()
    log.info("🚀 SuccuBot starting…")
    bot.run()
