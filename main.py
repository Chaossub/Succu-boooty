import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# ─── Import Handlers ────────────────────────────────────────────────────────
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer
)

# ─── Setup Scheduler ────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.start()

# ─── Register All Modules ───────────────────────────────────────────────────
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
flyer.register(app, scheduler)

# ─── Run the Bot ────────────────────────────────────────────────────────────
print("✅ SuccuBot is running...")
app.run()
