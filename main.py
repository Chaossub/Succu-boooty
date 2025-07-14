import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client

# ─── Load environment ──────────────────────────────────────────────────────────
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ─── Init scheduler ───────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(
    timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles")
)
scheduler.start()

# ─── Init bot ─────────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode="html",  # use lowercase html for Pyrogram v2
)

# ─── Import & register handlers ───────────────────────────────────────────────
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

# flyer needs the scheduler so it can reschedule persisted jobs on startup
flyer.register(app, scheduler)

print("✅ SuccuBot is running...")
app.run()

