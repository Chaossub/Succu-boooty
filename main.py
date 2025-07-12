import os
import logging
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# ─── Configure Logging ─────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Load Environment Variables ────────────────────────
load_dotenv = load_dotenv
load_dotenv()
API_ID    = int(os.getenv("API_ID"))
API_HASH  = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Default timezone to America/Los_Angeles if not set
TZ = os.getenv("SCHEDULER_TZ", "America/Los_Angeles")

# ─── Initialize Pyrogram Client ───────────────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# ─── Initialize and Start Scheduler ───────────────────
scheduler = AsyncIOScheduler(timezone=TZ)
scheduler.start()

# ─── Job Execution Listener ───────────────────────────
def job_listener(event):
    if event.exception:
        logger.error("Job %s failed: %s", event.job_id, event.exception)
    else:
        logger.info("Job %s executed successfully at %s", event.job_id, event.scheduled_run_time)

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# ─── Register Handler Modules ─────────────────────────
from handlers import welcome, help_cmd, moderation, federation, summon, xp, fun, flyer
from handlers.debug_thread import register as register_debug_thread
from handlers.thread_id import register as thread_id_register

# ─── Hook up all handlers ─────────────────────────────
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
register_debug_thread(app)
thread_id_register(app)

# ─── Flyer handlers with scheduler ────────────────────
flyer.register(app, scheduler)

logger.info("✅ SuccuBot is running (Scheduler TZ: %s)", TZ)
app.run()
