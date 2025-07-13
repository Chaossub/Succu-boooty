import os
from dotenv import load_dotenv
import logging
from pytz import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

# Load environment
load_dotenv()
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Initialize Pyrogram client
app = Client(
    'SuccuBot',
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Initialize scheduler with timezone
sched_tz = timezone(os.getenv('SCHEDULER_TZ', 'America/Los_Angeles'))
scheduler = BackgroundScheduler(timezone=sched_tz)

# Register handlers
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
# Flyer needs scheduler reference
flyer.register(app, scheduler)

# Start scheduler and bot
scheduler.start()
logging.info('✅ Scheduler started')
print('✅ Scheduler started')
print('✅ SuccuBot is running...')
app.run()
