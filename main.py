import os
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ── Load env & logging ──────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
log = logging.getLogger("SuccuBot")

# ── Telegram creds ─────────────────────────────────────────────────────────────
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise SystemExit("Missing API_ID/API_HASH/BOT_TOKEN in environment")

# ── Create Pyrogram client ─────────────────────────────────────────────────────
app = Client("succubot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ── Import all handlers ───────────────────────────────────────────────────────
import dm_foolproof
from handlers import (
    menu,
    help_panel,
    help_cmd,
    req_handlers,
    enforce_requirements,
    exemptions,
    membership_watch,
    flyer,
    flyer_scheduler,
    schedulemsg,
    warmup,
    hi,
    fun,
    warnings,
    moderation,
    federation,
    summon,
    xp,
    dmnow,
)

ALL_MODULES = [
    dm_foolproof,
    menu,
    help_panel,
    help_cmd,
    req_handlers,
    enforce_requirements,
    exemptions,
    membership_watch,
    flyer,
    flyer_scheduler,
    schedulemsg,
    warmup,
    hi,
    fun,
    warnings,
    moderation,
    federation,
    summon,
    xp,
    dmnow,
]

# ── Wire handlers only once ────────────────────────────────────────────────────
def wire_handlers_once():
    if getattr(app, "_succubot_handlers_loaded", False):
        return
    for mod in ALL_MODULES:
        if hasattr(mod, "register"):
            try:
                mod.register(app)
                log.info(f"wired: {mod.__name__}")
            except Exception as e:
                log.error(f"Failed to wire {mod.__name__}: {e}")
    setattr(app, "_succubot_handlers_loaded", True)
    log.info("Handlers wired.")

# ── Welcome banner + Main Menu ─────────────────────────────────────────────────
WELCOME_BANNER = os.getenv("WELCOME_BANNER", "").strip() or (
    "🔥 Welcome to Succubus Sanctuary 🔥\n"
    "Your naughty little helper is ready. Use the buttons below. 😈"
)

def _kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="contact_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="find_elsewhere")],
        [InlineKeyboardButton("❓ Help", callback_data="help_root")],
    ])

@app.on_message(filters.command(["start", "portal"]))
async def start_cmd(_, m: Message):
    await m.reply_text(
        WELCOME_BANNER,
        reply_markup=_kb_main(),
        disable_web_page_preview=True
    )

@app.on_message(filters.command("menu"))
async def menu_cmd(_, m: Message):
    await m.reply_text(
        WELCOME_BANNER,
        reply_markup=_kb_main(),
        disable_web_page_preview=True
    )

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("✅ Booting SuccuBot")
    wire_handlers_once()
    app.run()
