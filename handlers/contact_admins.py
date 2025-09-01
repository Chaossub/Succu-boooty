# handlers/contact_admins.py
# Contact Admins panel with DM buttons + suggestion / anonymous.

import os
import time
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
RONI_ID = int(os.getenv("RONI_ID", "0") or "0")
RUBY_ID = int(os.getenv("RUBY_ID", "0") or "0")
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

# ephemeral capture state for suggestion / anon
_pending: Dict[int, Tuple[str, float]] = {}
TTL = 5 * 60  # 5 minutes

def _kb_contact() -> InlineKeyboardMarkup:
    rows = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"💬 Message {RONI_NAME} ➜", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"💬 Message {RUBY_NAME} ➜", url=f"tg://user?id={RUBY_ID}")])
    rows += [
        [InlineKeyboardButton("💡 Send a suggestion", callback_data="contact_suggest")],
        [InlineKeyboardButton("🙈 Send anonymous message", callback_data="contact_anon")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_start")],
    ]
    return InlineKeyboardMarkup(rows)

async def _open_panel(c: Client, chat_id: int, mid: int | None = None):
    text = "👑 <b>Contact Admins</b>\nDM an admin directly or send a suggestion / anonymous message."
    if mid:
        await c.edit_message_text(chat_id, mid, text, reply_markup=_kb_contact(), disable_web_page_preview=True)
    else:
        await c.send_message(chat_id, text, reply_markup=_kb_contact(), disable_web_page_preview=True)

def _set_pending(uid: int, kind: str):
    _pending[uid] = (kind, time.time() + TTL)

def _get_pending(uid: int) -> str | None:
    now = time.time()
    # purge expired
    for k, (_, exp) in list(_pending.items()):
        if exp < now:
            _pending.pop(k, None)
    tup = _pending.get(uid)
    if not tup:
        return None
    kind, exp = tup
    return kind if exp >= now else None

def _clear_pending(uid: int):
    _pending.pop(uid, None)

def register(app: Client):

    # open from main menu button
    @app.on_callback_query(filters.regex("^dmf_contact_admins$"))
    async def _open_from_menu(c: Client, q: CallbackQuery):
        await _open_panel(c, q.message.chat.id, q.message.id)
        await q.answer()

    # suggestion / anonymous flows
    @app.on_callback_query(filters.regex("^contact_suggest$"))
    async def _suggest(c: Client, q: CallbackQuery):
        _set_pending(q.from_user.id, "suggest")
        await q.answer()
        await c.edit_message_text(
            q.message.chat.id, q.message.id,
            "💡 <b>Suggestion box</b>\nSend your suggestion as a single message within 5 minutes.\n"
            "Your username will be included.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Cancel", callback_data="dmf_contact_admins")]])
        )

    @app.on_callback_query(filters.regex("^contact_anon$"))
    async def _anon(c: Client, q: CallbackQuery):
        _set_pending(q.from_user.id, "anon")
        await q.answer()
        await c.edit_message_text(
            q.message.chat.id, q.message.id,
            "🙈 <b>Anonymous message</b>\nSend your message as a single text within 5 minutes.\n"
            "Your username will NOT be included.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Cancel", callback_data="dmf_contact_admins")]])
        )

    # capture next private message if a flow is active
    @app.on_message(filters.private & ~filters.command([]))
    async def _capture(c: Client, m: Message):
        kind = _get_pending(m.from_user.id)
        if not kind:
            return
        _clear_pending(m.from_user.id)

        if OWNER_ID:
            if kind == "suggest":
                u = m.from_user
                who = (u.first_name or "User").replace("<", "&lt;").replace(">", "&gt;")
                mention = f"<a href='tg://user?id={u.id}'>{who}</a>"
                text = f"💡 <b>Suggestion</b> from {mention} @{u.username or '—'}:\n\n{m.text or '(no text)'}"
                await c.send_message(OWNER_ID, text, disable_web_page_preview=True)
            else:
                text = f"🙈 <b>Anonymous message</b>:\n\n{m.text or '(no text)'}"
                await c.send_message(OWNER_ID, text, disable_web_page_preview=True)

        await c.send_message(m.chat.id, "✅ Thanks! Sent to the admins.", reply_markup=_kb_contact())
