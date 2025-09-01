# dm_foolproof.py
# Single source of truth for /start + DM-ready marking & owner alert.

import os, json, time, logging
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
# Comma-separated or single id (negative for supergroups)
_SANCTUARY_IDS = os.getenv("SANCTUARY_GROUP_IDS") or os.getenv("SANCTUARY_CHAT_ID") or ""
SANCTUARY_GROUP_IDS: List[int] = []
for part in _SANCTUARY_IDS.replace(" ", "").split(","):
    if part:
        try:
            SANCTUARY_GROUP_IDS.append(int(part))
        except ValueError:
            pass

# Button labels (keep in sync with your other handlers)
BTN_MENU   = os.getenv("BTN_MENU",  "💕 Menus")
BTN_ADMINS = os.getenv("BTN_ADMINS","👑 Contact Admins")
BTN_FIND   = os.getenv("BTN_FIND",  "🔥 Find Our Models Elsewhere")
BTN_HELP   = os.getenv("BTN_HELP",  "❓ Help")

# Callback IDs expected by your existing handlers
CB_MENU   = os.getenv("CB_MENU",   "open_menu")
CB_ADMINS = os.getenv("CB_ADMINS", "contact_admins")
CB_FIND   = os.getenv("CB_FIND",   "find_elsewhere")
CB_HELP   = os.getenv("CB_HELP",   "help_panel")

store = DMReadyStore()  # persists to data/dm_ready.json

def _kb_portal() -> InlineKeyboardMarkup:
    # Buttons are callbacks to your already-wired handlers
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_MENU,   callback_data=CB_MENU)],
        [InlineKeyboardButton(BTN_ADMINS, callback_data=CB_ADMINS)],
        [InlineKeyboardButton(BTN_FIND,   callback_data=CB_FIND)],
        [InlineKeyboardButton(BTN_HELP,   callback_data=CB_HELP)],
    ])

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def _format_user(u) -> str:
    handle = f"@{u.username}" if u and u.username else ""
    name = (u.first_name or "there")
    return f"{name} {handle}".strip()

async def _announce_owner_if_new(app: Client, user_id: int, user) -> None:
    if OWNER_ID <= 0:
        return
    if store.was_just_marked(user_id):  # only on first mark
        try:
            text = f"✅ <b>DM-ready</b> — {_format_user(user)}"
            await app.send_message(OWNER_ID, text)
        except Exception as e:
            log.warning("Owner DM-ready notify failed: %s", e)

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_portal(client: Client, m: Message):
        # Deep-link payloads: "d" means came from /dmnow button; anything else behaves the same
        payload: Optional[str] = None
        try:
            if m.text and " " in m.text:
                payload = m.text.split(" ", 1)[1].strip()
        except Exception:
            payload = None

        u = m.from_user
        uid = u.id if u else 0

        # Mark DM-ready exactly once (persists)
        if uid and not store.is_ready(uid):
            store.set_ready(uid, username=u.username, first_name=u.first_name)
            log.info("DM-ready NEW user %s (%s)", uid, _format_user(u))
            await _announce_owner_if_new(client, uid, u)

        # Reply with the portal (buttons only; no second handler touches /start)
        try:
            await m.reply_text(WELCOME_TEXT, reply_markup=_kb_portal(), disable_web_page_preview=True)
        except Exception:
            await client.send_message(m.chat.id, WELCOME_TEXT, reply_markup=_kb_portal(), disable_web_page_preview=True)
