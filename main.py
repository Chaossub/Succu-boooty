import os
import logging
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn
import threading

# ─── Load Env ───────────────────────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_NAME = os.getenv("SESSION_NAME", "SuccuBot")

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")

# ─── FastAPI Health Server ──────────────────────────────────────────────────
app_api = FastAPI()

@app_api.get("/")
async def root():
    return {"status": "ok"}

def run_api():
    uvicorn.run(app_api, host="0.0.0.0", port=8000)

# ─── Start FastAPI in a thread ──────────────────────────────────────────────
threading.Thread(target=run_api).start()
logger.info("✅ Health server running. Starting bot...")

# ─── Pyrogram Bot Client ────────────────────────────────────────────────────
app = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Start Scheduler ────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Import and Register Handlers ───────────────────────────────────────────
from handlers import (
    federation,
    flyer,
    fun,
    get_id,
    help_cmd,
    moderation,
    summon,
    test,
    warnings,
    welcome,
    xp,
)

federation.register(app)
flyer.register(app)
fun.register(app)
get_id.register(app)
help_cmd.register(app)
moderation.register(app)
summon.register(app)
test.register(app)
warnings.register(app)
welcome.register(app)
xp.register(app)

logger.info("✅ All handlers registered.")

# ─── Run the Bot ────────────────────────────────────────────────────────────
app.run()
