import os
import threading
import logging

from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")

# ─── Env ─────────────────────────────────────────────────────────────────────
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ─── Pyrogram Client ─────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Scheduler ───────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="UTC")

# ─── Health Server ───────────────────────────────────────────────────────────
app_fastapi = FastAPI()

@app_fastapi.get("/")
def read_root():
    return {"status": "ok"}

def run_health_server():
    logger.info("✅ Health server running. Starting bot...")
    uvicorn.run(app_fastapi, host="0.0.0.0", port=8000)

# ─── Register Handlers ───────────────────────────────────────────────────────
def register_all_handlers():
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

# ─── Main Entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    scheduler.start()
    logger.info("⏰ Scheduler started.")
    
    threading.Thread(target=run_health_server, daemon=True).start()
    register_all_handlers()
    app.run()
