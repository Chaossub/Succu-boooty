# dm_foolproof.py
# SINGLE /start with a tiny dedup so welcome doesn't double-send.
import os, time, json
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

_DEDUP_FILE = Path("data/_start_seen.json")
_DEDUP_FILE.parent.mkdir(parents=True, exist_ok=True)
_DEDUP_TTL_SEC = 12

def _is_duplicate_start(chat_id: int) -> bool:
    now = time.time()
    try:
        data = json.loads(_DEDUP_FILE.read_text()) if _DEDUP_FILE.exists() else {}
    except Exception:
        data = {}
    data = {k: v for k, v in data.items() if now - v < _DEDUP_TTL_SEC}
    last = data.get(str(chat_id), 0)
    is_dup = (now - last) < _DEDUP_TTL_SEC
    data[str(chat_id)] = now
    try:
        _DEDUP_FILE.write_text(json.dumps(data))
    except Exception:
        pass
    return is_dup

MENU_LABEL   = os.getenv("MENU_BTN", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_BTN", "👑 Contact Admins")
FIND_LABEL   = os.getenv("FIND_MODELS_BTN", "🔥 Find Our Models Elsewhere")
HELP_LABEL   = os.getenv("HELP_BTN", "❓ Help")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def _kb() -> InlineKeyboardMarkup:
    # Keep the same callback datas you already use in panels.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(MENU_LABEL,   callback_data="nav:main")],
        [InlineKeyboardButton(ADMINS_LABEL, callback_data="nav:admins")],
        [InlineKeyboardButton(FIND_LABEL,   callback_data="nav:find")],
        [InlineKeyboardButton(HELP_LABEL,   callback_data="nav:help")],
    ])

def register(app: Client):
    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        if _is_duplicate_start(m.chat.id):
            return
        await m.reply_text(WELCOME_TEXT, reply_markup=_kb(), disable_web_page_preview=True)

