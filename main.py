import os
import logging
import importlib
import pkgutil
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
import uvicorn
import threading

# ─── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")

# ─── Env Setup ─────────────────────────────────────────────────────
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ─── Pyrogram Client ───────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Scheduler ─────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.start()
logger.info("⏰ Scheduler started.")

# ─── Healthcheck Server (for Railway) ──────────────────────────────
fastapi_app = FastAPI()

@fastapi_app.get("/")
async def root():
    return {"status": "ok"}

def run_health_server():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

threading.Thread(target=run_health_server, daemon=True).start()
logger.info("✅ Health server running. Starting bot...")

# ─── Handler Loader ────────────────────────────────────────────────
for module_info in pkgutil.iter_modules(["handlers"]):
    module_name = module_info.name
    module = importlib.import_module(f"handlers.{module_name}")
    if hasattr(module, "register"):
        module.register(app)
        logger.info(f"Registered handler: handlers.{module_name}.register")

# ─── Run the Bot ───────────────────────────────────────────────────
app.run()
