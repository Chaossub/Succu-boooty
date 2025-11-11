# handlers/contact_admins.py
# Contact Roni / Ruby + Suggestions + Anonymous message to OWNER_ID.

import os, logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

log = logging.getLogger("contact_admins")

def _to_int(val: str | None) -> int | None:
    try:
        return int(val) if val and val.isdigit() else None
    except Exception:
        return None

OWNER_ID  = _to_int(os.getenv("OWNER_ID"))
RONI_ID   = _to_int(os.getenv("RONI_ID"))
RUBY_ID   = _to_int(os.getenv("RUBY_ID"))
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
SUGGESTIONS_URL = os.getenv("SUGGESTIONS_URL", "")  # optional link

BTN_BACK = "⬅️ Back to Main"

# Small in-memory state for anonymous messages
_PENDING_ANON: set[int] = set()

CONTACT_COPY = (
    "👑 <b>Contact Admins</b>\n\n"
    "• Tap a button below to DM an admin\n"
    "• Or send an anonymous message via the bot (goes to the owner only)."
)

def _kb_contact() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"👑 Message {RONI_NAME}", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"👑 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    if SUGGESTIONS_URL:
        rows.append([InlineKeyboardButton("💡 Suggestions", url=SUGGESTIONS_URL)])
    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="contact:anon")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="home:main")])
    return InlineKeyboardMarkup(rows)

def _kb_back_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="home:main")]])

async def render_contact(client: Client, target_message: Message, edit: bool = True):
    kb = _kb_contact()
    if edit:
        try:
            await target_message.edit_text(CONTACT_COPY, reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            pass
    await client.send_message(target_message.chat.id, CONTACT_COPY, reply_markup=kb, disable_web_page_preview=True)

def register(app: Client):

    # Main entry from the home panel button
    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_contact(client: Client, q: CallbackQuery):
        try:
            await q.message.edit_text(CONTACT_COPY, reply_markup=_kb_contact(), disable_web_page_preview=True)
        finally:
            await q.answer()

    # Optional command aliases
    @app.on_message(filters.private & filters.command(["contactadmins","contact","admins"]))
    async def cmd_contact(client: Client, m: Message):
        await render_contact(client, m.reply_to_message or m, edit=False)

    # Begin anonymous flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        _PENDING_ANON.add(q.from_user.id)
        text = (
            "🕵️ <b>Anonymous Message</b>\n"
            "Send me the message now (text only). I’ll forward it anonymously to the owner."
        )
        try:
            await q.message.edit_text(text, reply_markup=_kb_back_only(), disable_web_page_preview=True)
        finally:
            await q.answer()

    # Collect the next private text as the anonymous message
    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        if uid not in _PENDING_ANON:
            return
        if not OWNER_ID:
            await m.reply_text("Owner is not configured.", reply_markup=_kb_back_only())
            _PENDING_ANON.discard(uid)
            return
        try:
            await client.send_message(
                OWNER_ID,
                f"🕵️ Anonymous message:\n\n{m.text}"
            )
            await m.reply_text("✅ Sent anonymously.", reply_markup=_kb_back_only())
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await m.reply_text("❌ Couldn’t send right now.", reply_markup=_kb_back_only())
        finally:
            _PENDING_ANON.discard(uid)

    log.info("contact_admins wired")
