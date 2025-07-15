import os
import logging
from dotenv import load_dotenv

print("MAIN.PY BOOTSTRAP BEGIN")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("root")
load_dotenv()
log.info("Loaded environment.")

from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
scheduler.start()
log.info("Scheduler started.")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

log.info("Registering handlers...")
try:
    from handlers import (
        welcome,
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        flyer,
        flyer_scheduler,  # NEW: robust scheduler module!
    )
    welcome.register(app)
    log.info("Registered welcome.")
    help_cmd.register(app)
    log.info("Registered help_cmd.")
    moderation.register(app)
    log.info("Registered moderation.")
    federation.register(app)
    log.info("Registered federation.")
    summon.register(app)
    log.info("Registered summon.")
    xp.register(app)
    log.info("Registered xp.")
    fun.register(app)
    log.info("Registered fun.")
    flyer.register(app)
    log.info("Registered flyer.")
    flyer_scheduler.register(app, scheduler)  # NEW: scheduler handler takes scheduler!
    log.info("Registered flyer_scheduler.")
except Exception as e:
    log.error(f"🔥 Exception during handler registration: {e}", exc_info=True)
    raise

log.info("✅ SuccuBot is running...")
try:
    app.run()
except Exception as e:
    log.error(f"🔥 Exception during app.run(): {e}", exc_info=True)
    raise
