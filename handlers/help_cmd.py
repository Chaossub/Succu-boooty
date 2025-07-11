import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Load environment variables
load_dotenv()

API_ID   = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN= os.getenv("BOT_TOKEN")

# Initialize the bot client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

# Initialize and start the AsyncIO scheduler
scheduler = AsyncIOScheduler(timezone=os.environ.get("SCHEDULER_TZ", "US/Pacific"))
scheduler.start()

# Add a listener to log successes and failures
def job_listener(event):
    if event.exception:
        print(f"[Scheduler] Job {event.job_id} FAILED: {event.exception!r}")
    else:
        print(f"[Scheduler] Job {event.job_id} ran successfully at {event.scheduled_run_time!r}")

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# Import and register all handler modules
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

# Register flyer handlers with the scheduler
flyer.register(app, scheduler)

print("✅ SuccuBot is running...")
app.run()
