import os
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Optional: Set time zone for scheduler
SCHEDULER_TZ = os.environ.get("SCHEDULER_TZ", "UTC")

# Set up group shortcuts from environment
SUCCUBUS_SANCTUARY = os.environ.get("SUCCUBUS_SANCTUARY")
MODELS_CHAT = os.environ.get("MODELS_CHAT")
TEST_GROUP = os.environ.get("TEST_GROUP")

GROUP_SHORTCUTS = {
    "SUCCUBUS_SANCTUARY": SUCCUBUS_SANCTUARY,
    "MODELS_CHAT": MODELS_CHAT,
    "TEST_GROUP": TEST_GROUP
}

# Initialize the bot
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Initialize scheduler
scheduler = BackgroundScheduler(timezone=SCHEDULER_TZ)
scheduler.start()

# ─── Register Handlers ─────────────────────────────────────────────
def register_all_handlers(app):
    from handlers import (
        help_cmd,
        moderation,
        federation,
        summon,
        xp,
        fun,
        welcome,
        flyer
    )

    help_cmd.register(app)
    moderation.register(app)
    federation.register(app)
    summon.register(app)
    xp.register(app)
    fun.register(app)
    welcome.register(app)
    flyer.register(app, scheduler)  # now accepts scheduler

print("✅ SuccuBot is running...")
register_all_handlers(app)
app.run()

