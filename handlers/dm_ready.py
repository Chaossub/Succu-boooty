# handlers/dm_ready.py
from __future__ import annotations
import os
import time
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

# Use your existing JSON-backed store (already in your repo)
# Falls back to JSON and persists across restarts.
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_ready")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

_store = DMReadyStore()

def _fmt_owner_line(user) -> str:
    uname = f"@{user.username}" if getattr(user, "username", None) else ""
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    return f"✅ <b>DM-ready</b>: {user.first_name or 'User'} {uname}\n<code>{user.id}</code> • {ts}Z"

async def _mark_dm_ready_once(client: Client, m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    u = m.from_user
    # Check if already recorded
    already = _store.get(u.id)
    if already:
        return
    # Persist basic info
    _store.add({
        "id": u.id,
        "user_id": u.id,               # for compatibility with older tools
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "username": u.username or "",
        "ts": int(time.time()),
    })
    # Notify owner quietly; ignore errors
    if OWNER_ID:
        try:
            await client.send_message(OWNER_ID, _fmt_owner_line(u))
        except Exception:
            pass

def register(app: Client):

    # Expose a remover hook for cleanup/watch modules
    async def _remove(uid: int):
        try:
            _store.remove_dm_ready_global(uid)
        except Exception:
            pass
    setattr(app, "_succu_dm_store_remove", _remove)

    @app.on_message(filters.private & filters.command("start"))
    async def _start(client: Client, m: Message):
        # 1) mark DM-ready once
        await _mark_dm_ready_once(client, m)
        # 2) send the welcome with single, consistent UI
        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True
        )
        log.info("Handled /start for %s", m.from_user.id if m.from_user else "unknown")
