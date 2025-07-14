import os
import logging
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# ─── Set logging levels to hide Pyrogram and APScheduler debug spam ──────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pyrogram.session.session").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ─── Load environment ────────────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Init scheduler ──────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(
    timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
)
scheduler.start()

# ─── Init bot ────────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Import & register handlers ──────────────────────────────────────────────
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
)

welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)

# Flyer needs the scheduler so it can reschedule persisted jobs on startup
flyer.register(app, scheduler)

print("✅ SuccuBot is running...")

# ─── Block forever so Railway/Heroku doesn't kill the process ────────────────
try:
    app.run()
    # This line is only reached if the bot is stopped or crashes.
    import time
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    print("Bot stopped by user.")

