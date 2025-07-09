import os
import logging
import asyncio
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from fastapi import FastAPI
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── Load .env ─────────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Bot ──────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Scheduler ────────────────────────────────────────────────
scheduler = AsyncIOScheduler()
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Health Check ─────────────────────────────────────────────
web_app = FastAPI()

@web_app.get("/")
async def health_check():
    return {"status": "ok"}

# ─── Register Handlers ────────────────────────────────────────
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
    xp
)

for module in [federation, flyer, fun, get_id, help_cmd, moderation, summon, test, warnings, welcome, xp]:
    module.register(app)
    logger.info(f"✅ Registered handler: handlers.{module.__name__.split('.')[-1]}")

# Start the flyer scheduler
flyer.scheduler.start()

# ─── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("✅ Health server running. Starting bot...")

    async def main():
        await app.start()
        await asyncio.Event().wait()  # Run forever

    loop = asyncio.get_event_loop()
    loop.create_task(main())

    uvicorn.run(web_app, host="0.0.0.0", port=8000)
