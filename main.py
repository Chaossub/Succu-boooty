import os
import logging
import asyncio
from pyrogram import Client
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
import uvicorn

# ─── Load env ─────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB_NAME")

# ─── Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Scheduler ─────────────────────────────────────
scheduler = AsyncIOScheduler()

# ─── Bot and App ───────────────────────────────────
bot = Client("SuccuBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
api = FastAPI()


@api.get("/")
def root():
    return {"status": "ok", "message": "SuccuBot is running!"}


# ─── Main Async Entry ──────────────────────────────
async def main():
    try:
        logger.info("⏰ Scheduler started.")
        scheduler.start()

        await bot.start()

        # Register all handlers
        from handlers import (
            welcome,
            help_cmd,
            moderation,
            federation,
            summon,
            xp,
            fun,
            flyer,
            get_id,
            warnings,
            test,
        )

        for handler in [
            welcome,
            help_cmd,
            moderation,
            federation,
            summon,
            xp,
            fun,
            flyer,
            get_id,
            warnings,
            test,
        ]:
            handler.register(bot)
            logger.info(f"✅ Registered handler: handlers.{handler.__name__}")

        logger.info("✅ All handlers registered. Starting bot...")

        await idle()  # keeps it running

    except Exception as e:
        logger.exception(f"Unhandled error in main(): {e}")
    finally:
        await bot.stop()
        logger.info("🚫 Bot stopped.")


# ─── Idle Function ─────────────────────────────────
async def idle():
    while True:
        await asyncio.sleep(3600)


# ─── Launch FastAPI ────────────────────────────────
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    uvicorn.run(api, host="0.0.0.0", port=8000)
