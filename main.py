import os
import logging
from dotenv import load_dotenv

print("MAIN.PY BOOTSTRAP BEGIN")

logging.basicConfig(level=logging.INFO)
load_dotenv()
print("Loaded environment.")

from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import Client
from pyrogram.enums import ParseMode

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

scheduler = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "America/Los_Angeles"))
scheduler.start()
print("Scheduler started.")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML,
)

print("Registering handlers...")
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
    )
    print("Imported all handler modules.")
    welcome.register(app)
    print("Registered welcome.")
    help_cmd.register(app)
    print("Registered help_cmd.")
    moderation.register(app)
    print("Registered moderation.")
    federation.register(app)
    print("Registered federation.")
    summon.register(app)
    print("Registered summon.")
    xp.register(app)
    print("Registered xp.")
    fun.register(app)
    print("Registered fun.")
    flyer.register(app, scheduler)
    print("Registered flyer.")
except Exception as e:
    print(f"🔥 Exception during handler registration: {e}")
    import traceback; traceback.print_exc()
    raise

print("✅ SuccuBot is running...")
try:
    app.run()
except Exception as e:
    print(f"🔥 Exception during app.run(): {e}")
    import traceback; traceback.print_exc()
    raise
