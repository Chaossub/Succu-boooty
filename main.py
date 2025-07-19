import os
import asyncio
from pyrogram import Client
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import all handlers (import after app so set_main_loop is available!)
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
    flyer_scheduler,
    warnings,
    warmup,
    hi,
    schedulemsg
)

# --- SET MAIN EVENT LOOPS FOR SCHEDULERS BEFORE ANY .register(app) ---
flyer_scheduler.set_main_loop(asyncio.get_event_loop())
schedulemsg.set_main_loop(asyncio.get_event_loop())

# Register handlers (all should have register(app))
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
warnings.register(app)
flyer.register(app)
warmup.register(app)
hi.register(app)
schedulemsg.register(app)

# Register the flyer scheduler (must be after set_main_loop above)
flyer_scheduler.register(app)

print("✅ SuccuBot is running...")

if __name__ == "__main__":
    app.run()
