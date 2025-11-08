import os
import logging
from dotenv import load_dotenv
from pyrogram import Client, idle

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

# ───────────────────────────────────────────────
# Environment setup
# ───────────────────────────────────────────────
API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = os.getenv("OWNER_ID", "6964994611")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise SystemExit("Missing API_ID, API_HASH, or BOT_TOKEN")

os.environ["OWNER_ID"] = str(OWNER_ID)
log.info("👑 OWNER_ID = %s", OWNER_ID)

# ───────────────────────────────────────────────
# Initialize Pyrogram
# ───────────────────────────────────────────────
app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

# ───────────────────────────────────────────────
# Module import helper
# ───────────────────────────────────────────────
def wire(module_path: str):
    try:
        mod = __import__(module_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Wired: %s", module_path)
        else:
            log.warning("⚠️ %s has no register() function", module_path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", module_path, e)

# ───────────────────────────────────────────────
# Load handlers — uses dm_ready_admin instead of dmready_admin
# ───────────────────────────────────────────────
MODULES = [
    "handlers.dm_ready",         # main DM ready handler
    "handlers.dm_ready_admin",   # ✅ your existing filename (underscore)
    "handlers.panels",
    "handlers.menu",
]

if __name__ == "__main__":
    for m in MODULES:
        wire(m)
    log.info("🚀 SuccuBot started successfully!")
    app.start()
    idle()
    app.stop()

