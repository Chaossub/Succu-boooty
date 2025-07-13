import os
import logging
from dotenv import load_dotenv
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# — Load environment —
load_dotenv()
API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# — Configure logging —
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# — Initialize Pyrogram client —
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# — Initialize AsyncIO scheduler with your TZ —
sched_tz  = timezone(os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
scheduler = AsyncIOScheduler(timezone=sched_tz)

# — Register all handlers —
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

welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)

# flyer needs the scheduler reference
flyer.register(app, scheduler)

# — Start the scheduler —
scheduler.start()
logger.info("✅ AsyncIO Scheduler started")

# — Run the bot (this will drive both Pyrogram and AsyncIO) —
app.run()
