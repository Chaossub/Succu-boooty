# dm_foolproof.py
# Single welcome card with inline buttons like the screenshot; no reply-keyboard.

import os
from contextlib import suppress
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# Optional requirement store (used to mark DM-ready once)
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# ---------- ENV ----------
FIND_ELSEWHERE_URL = os.getenv("FIND_ELSEWHERE_URL", "https://example.com/models")

def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in {OWNER_ID, SUPER_ADMIN_ID})

# ---------- UI ----------
WELCOME_TEXT = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models_all")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", url=FIND_ELSEWHERE_URL)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def _dm_ready_line(u) -> str:
    # Prefer @username; fall back to display name; never leak numeric ID in the chat
    if getattr(u, "username", None):
        who = f"@{u.username}"
    else:
        who = (u.first_name or "User")
    return f"✅ **DM-ready** — {who} just opened the portal."

# ---------- Wire ----------
def register(app: Client):
    @app.on_message(filters.private & filters.command(["start", "portal"]))
    async def start_cmd(client: Client, m: Message):
        u = m.from_user
        if not u or u.is_bot:
            return

        # 1) Mark DM-ready globally (one-time) unless owner/super admin
        if not _is_admin(u.id) and _store:
            with suppress(Exception):
                # Only flip to True if not already True
                current = _store.get_dm_ready_global(u.id)
                if not current:
                    _store.set_dm_ready_global(u.id, True)
                    await m.reply_text(_dm_ready_line(u))

        # 2) Send the welcome card with INLINE buttons (like your screenshot)
        await client.send_message(
            chat_id=m.chat.id,
            text=WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True
        )
