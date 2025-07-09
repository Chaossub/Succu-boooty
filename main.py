import os
import logging
from dotenv import load_dotenv
from threading import Thread
from fastapi import FastAPI
import uvicorn

from pyrogram import Client
from pyrogram.enums import ParseMode

# Load environment variables
load_dotenv()

# ─── Logging ─────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── FastAPI Health Server ──────────────────────────
app_api = FastAPI()

@app_api.get("/")
def read_root():
    return {"status": "ok"}

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app_api, host="0.0.0.0", port=port)

Thread(target=run_health_server).start()
logger.info("✅ Health server running. Starting bot...")

# ─── Telegram Bot Client ────────────────────────────
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Handler Registration ───────────────────────────
from handlers import (
    welcome, help_cmd, moderation, federation,
    summon, xp, fun, flyer, warnings, get_id, test
)

for mod in [
    welcome, help_cmd, moderation, federation,
    summon, xp, fun, flyer, warnings, get_id, test
]:
    mod.register(app)
    logger.info(f"✅ Registered handler: handlers.{mod.__name__}")

# ─── Run Bot ────────────────────────────────────────
app.run()
