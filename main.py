# main.py
import os, logging
from dotenv import load_dotenv
from pyrogram import Client, idle

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

API_ID = int(os.getenv("API_ID", "0") or "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = os.getenv("OWNER_ID", "6964994611")
os.environ["OWNER_ID"] = str(OWNER_ID)

# Path for JSON persistence (create folder if needed)
os.environ.setdefault("DMREADY_DB", "data/dm_ready.json")

if not (API_ID and API_HASH and BOT_TOKEN):
    raise SystemExit("Missing API_ID, API_HASH, or BOT_TOKEN")

app = Client(
    "succubot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

def wire(path: str):
    try:
        mod = __import__(path, fromlist=["register"])
        mod.register(app)
        log.info("✅ Wired: %s", path)
    except Exception as e:
        log.error("❌ Failed to wire %s: %s", path, e)

MODULES = [
    "handlers.dm_ready",
    "handlers.dm_ready_admin",  # admin list/remove/clear, LA time
    # add your other modules here…
]

if __name__ == "__main__":
    for m in MODULES:
        wire(m)
    log.info("👑 OWNER_ID = %s", OWNER_ID)
    log.info("🚀 SuccuBot starting…")
    app.start()
    idle()
    app.stop()


