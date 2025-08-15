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

# ================== NEW: Requirements system wiring ==================
from req_handlers import wire_requirements_handlers
import req_handlers  # for adjusting DEFAULT_GROUP_ID and ADMINS at runtime

# -- Default group for /kickdefaulters (optional; can leave unset)
_default_gid = os.getenv("REQ_DEFAULT_GROUP_ID")
if _default_gid:
    try:
        req_handlers.DEFAULT_GROUP_ID = int(_default_gid)
    except Exception:
        print("WARN: REQ_DEFAULT_GROUP_ID is not a valid integer chat id.")

# -- Hard-wire OWNER (Roni), and allow additional admins via env
req_handlers.ADMINS.add(6964994611)  # <- YOUR TELEGRAM ID (owner, always recognized)

_extra_admins = os.getenv("REQ_EXTRA_ADMINS", "").strip()  # e.g. "111111111,222222222"
if _extra_admins:
    try:
        extra_ids = {int(x) for x in _extra_admins.split(",") if x.strip()}
        req_handlers.ADMINS |= extra_ids
    except Exception:
        print("WARN: REQ_EXTRA_ADMINS is not a comma-separated list of integers.")
# =====================================================================

# Import all existing handlers (import after app)
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

# Register existing handlers (all should have register(app))
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

# Register the flyer scheduler
flyer_scheduler.register(app)

# ================== NEW: Register requirements handlers ==================
wire_requirements_handlers(app)
# ========================================================================

print("✅ SuccuBot is running...")

if __name__ == "__main__":
    app.run()

