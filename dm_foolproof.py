# dm_foolproof.py
# SINGLE, idempotent /start. Stops duplicate "Welcome" bursts without changing your buttons.

import os
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# --- tiny in-memory de-dup window to ignore a 2nd /start burst
_RECENT_STARTS = {}         # chat_id -> last_ts
_START_TTL_SEC = 10         # keep it small; just prevents back-to-back duplicates

def _is_duplicate_start(chat_id: int) -> bool:
    now = time.time()
    last = _RECENT_STARTS.get(chat_id, 0)
    _RECENT_STARTS[chat_id] = now
    return (now - last) < _START_TTL_SEC

# --- button labels pulled from your existing .env (unchanged semantics)
MENU_LABEL   = os.getenv("MENU_BTN", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_BTN", "👑 Contact Admins")
FIND_LABEL   = os.getenv("FIND_MODELS_BTN", "🔥 Find Our Models Elsewhere")
HELP_LABEL   = os.getenv("HELP_BTN", "❓ Help")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def _start_kb() -> InlineKeyboardMarkup:
    # NOTE: layout/labels unchanged — still driven by your .env
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(MENU_LABEL,   callback_data="nav:main")],
        [InlineKeyboardButton(ADMINS_LABEL, callback_data="nav:admins")],
        [InlineKeyboardButton(FIND_LABEL,   callback_data="nav:find")],
        [InlineKeyboardButton(HELP_LABEL,   callback_data="nav:help")],
    ])

def register(app: Client):
    # This must be the ONLY /start in the whole project.
    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        # Hard stop duplicates without touching any other behavior
        if _is_duplicate_start(m.chat.id):
            return
        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_start_kb(),
            disable_web_page_preview=True
        )

