import os
import logging
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

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
log.info("👑 OWNER_ID = %s", OWNER_ID)

# ---------------- Pyrogram app ----------------
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=int(os.getenv("PYROGRAM_WORKERS", "16")),
    in_memory=False,
)

# Modules to wire (order matters; put core first).
# NOTE: No legacy /start handlers here except dm_foolproof (simple welcome UI).
MODULES: List[str] = [
    # DM-ready core
    "handlers.dm_ready",          # marks DM-ready on /start + owner ping
    "handlers.dm_ready_admin",    # /dmreadylist /dmreadyremove /dmreadyclear /dmreadydebug
    "handlers.dmready_watch",     # removes DM-ready on leave/kick/ban
    "handlers.dmready_cleanup",   # (alt) member-updated cleanup

    # UI shell (single /start welcome)
    "dm_foolproof",               # simple welcome + home buttons (no DM-ready logic)

    # Panels / menus
    "handlers.panels",
    "handlers.menu",
    "handlers.contact_admins",
    "handlers.help_panel",

    # Requirements / flyers / scheduling
    "handlers.enforce_requirements",
    "handlers.req_handlers",
    "handlers.flyer",
    "handlers.flyer_scheduler",
    "handlers.schedulemsg",

    # Moderation / federation / fun / misc
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

def wire(module_path: str):
    try:
        mod = __import__(module_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", module_path)
        else:
            log.warning("ℹ️ Module has no register(): %s", module_path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", module_path, e, exc_info=True)

# ---------------- FastAPI (optional) ----------------
fast = FastAPI(title="SuccuBot Worker", version="1.0")

@fast.get("/")
def root():
    return {"ok": True, "bot": "SuccuBot"}

def run_http():
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(fast, host="0.0.0.0", port=port, log_level="info")

# ---------------- Entrypoint ----------------
if __name__ == "__main__":
    # Ensure local persistence dir exists for JSON fallbacks
    os.makedirs("data", exist_ok=True)

    # Wire all modules
    for m in MODULES:
        wire(m)

    # Start both bot and http server
    from threading import Thread
    t = Thread(target=run_http, daemon=True)
    t.start()

    log.info("🚀 SuccuBot starting…")
    app.run()

