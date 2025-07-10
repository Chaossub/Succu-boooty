import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

# ─── ENV VARS ────────────────────────────────────────────────────────────────
API_ID     = int(os.getenv("API_ID"))
API_HASH   = os.getenv("API_HASH")
BOT_TOKEN  = os.getenv("BOT_TOKEN")
MONGO_URI  = os.getenv("MONGO_URI")
MONGO_DB   = os.getenv("MONGO_DB_NAME")

# Group Shortcuts must be in .env
os.environ["SUCCUBUS_SANCTUARY"] = os.getenv("SUCCUBUS_SANCTUARY")
os.environ["MODELS_CHAT"] = os.getenv("MODELS_CHAT")
os.environ["TEST_GROUP"] = os.getenv("TEST_GROUP")

# ─── INIT ────────────────────────────────────────────────────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()

# ─── REGISTER HANDLERS ───────────────────────────────────────────────────────
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
    flyer.register(app, scheduler)

# ─── RUN BOT ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("✅ SuccuBot is running...")
    register_all_handlers(app)
    app.run()
