import os
import logging
import threading

from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

from fastapi import FastAPI
import uvicorn

# ─── Environment & Logging ─────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
TZ        = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
PORT      = int(os.getenv("PORT", 8000))

# ─── Pyrogram Bot ───────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── AsyncIO Scheduler ─────────────────────────────────────────────────────────
sched_tz   = timezone(TZ)
scheduler  = AsyncIOScheduler(timezone=sched_tz)

# ─── FastAPI “Keep-Alive” ───────────────────────────────────────────────────────
api = FastAPI()

@api.get("/")
async def root():
    return {"status": "ok"}

def run_api():
    """Run uvicorn in a separate thread so it doesn’t block Pyrogram."""
    uvicorn.run(
        api,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )

# ─── Register Handlers ─────────────────────────────────────────────────────────
from handlers import (
    welcome, help_cmd, moderation, federation,
    summon, xp, fun, flyer
)
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
# flyer needs the scheduler reference:
flyer.register(app, scheduler)

# ─── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1) Start FastAPI so your platform sees an open HTTP port
    threading.Thread(target=run_api, daemon=True).start()
    logger.info(f"🚀 FastAPI server started on port {PORT}")

    # 2) Start the AsyncIO scheduler
    scheduler.start()
    logger.info("✅ AsyncIO Scheduler started")

    # 3) Run your Telegram bot (this hands control to Pyrogram’s loop)
    app.run()
