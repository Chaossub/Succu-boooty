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

# === Existing handlers ===
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

# --- SET MAIN EVENT LOOP FOR ALL SCHEDULERS ---
event_loop = asyncio.get_event_loop()
flyer_scheduler.set_main_loop(event_loop)
schedulemsg.set_main_loop(event_loop)

# Register existing handlers
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
flyer_scheduler.register(app)

# === Requirements module ===
from handlers.req_handlers import wire_requirements_handlers
wire_requirements_handlers(app)

# === Foolproof DM module ===
from dm_foolproof import register as register_dm_foolproof
register_dm_foolproof(app)

print("✅ SuccuBot is running...")

if __name__ == "__main__":
    app.run()
