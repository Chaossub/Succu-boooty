# dm_foolproof.py
# Private /start portal + DM-ready tracking (persists via dmready_store) with dedupe.
from __future__ import annotations
import os, logging, time
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.dmready_store import global_store as store

log = logging.getLogger("dm_foolproof")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

WELCOME_TITLE = "🔥 <b>Welcome to SuccuBot</b> 🔥"
WELCOME_BODY  = (
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

BTN_MENUS  = os.getenv("BTN_MENU", "💕 Menus")
BTN_ADMINS = "👑 Contact Admins"
BTN_FIND   = "🔥 Find Our Models Elsewhere"
BTN_HELP   = "❓ Help"

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_MENUS,  callback_data="dmf_open_menu")],
        [InlineKeyboardButton(BTN_ADMINS, callback_data="dmf_contact_admins")],
        [InlineKeyboardButton(BTN_FIND,   callback_data="dmf_find_models")],
        [InlineKeyboardButton(BTN_HELP,   callback_data="dmf_help")],
    ])

# ---------------------------------------------------------------------------
# Dedupe: avoid double execution from any race/duplicate update delivery
# key=(chat_id, message_id, 'start')  / also per-user short window
_recent: Dict[Tuple[int, int, str], float] = {}
_last_by_user: Dict[int, float] = {}
DEDUP_MSG_WINDOW = 5.0    # seconds per same message id
DEDUP_USER_WINDOW = 3.0   # seconds per user

def _seen(chat_id: int, message_id: int, user_id: int) -> bool:
    now = time.time()
    k = (chat_id, message_id, "start")
    # same message again?
    if now - _recent.get(k, 0.0) < DEDUP_MSG_WINDOW:
        return True
    _recent[k] = now
    # too soon for same user?
    if now - _last_by_user.get(user_id, 0.0) < DEDUP_USER_WINDOW:
        return True
    _last_by_user[user_id] = now
    # garbage collect old entries
    for kk, ts in list(_recent.items()):
        if now - ts > 5 * DEDUP_MSG_WINDOW:
            _recent.pop(kk, None)
    for uid, ts in list(_last_by_user.items()):
        if now - ts > 5 * DEDUP_USER_WINDOW:
            _last_by_user.pop(uid, None)
    return False
# ---------------------------------------------------------------------------

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_portal(client: Client, m: Message):
        u = m.from_user
        if not u:
            return

        # Dedupe guard — if this exact message (or same user within a tight window)
        # was already processed, bail out.
        if _seen(m.chat.id, m.id or 0, u.id):
            return

        # Mark once (persisted)
        newly = store.add(u.id, u.first_name, u.username)
        if newly:
            log.info(f"DM-ready NEW user {u.id} ({u.first_name})")
            if OWNER_ID:
                uname = f"@{u.username}" if u.username else ""
                try:
                    await client.send_message(OWNER_ID, f"✅ DM-ready — {u.first_name} {uname}".strip())
                except Exception as e:
                    log.warning(f"Owner notify failed: {e}")

        # Send/refresh the DM portal
        try:
            await m.reply_text(
                f"{WELCOME_TITLE}\n{WELCOME_BODY}",
                reply_markup=kb_main(),
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning(f"/start portal send failed: {e}")
