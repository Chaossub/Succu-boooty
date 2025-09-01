# handlers/contact_admins.py
# Contact Roni / Ruby + Suggestions + Anonymous message to OWNER_ID.

import os, logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

log = logging.getLogger("contact_admins")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
RONI_ID  = os.getenv("RONI_ID")
RUBY_ID  = os.getenv("RUBY_ID")
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
SUGGESTIONS_URL = os.getenv("SUGGESTIONS_URL", "")  # optional link

BTN_BACK = "⬅️ Back to Main"

# Small in-memory state for anonymous messages
_PENDING_ANON = set()

CONTACT_COPY = (
    "👑 <b>Contact Admins</b>\n\n"
    "• Tag an admin in chat\n"
    "• Or send an anonymous message via the bot."
)

def _kb_contact(bot_username: str) -> InlineKeyboardMarkup:
    rows = []
    # Deep-link DM buttons (open the bot with a tag prefilled)
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME}", url=f"https://t.me/{bot_username}?start=dmnow")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME}", url=f"https://t.me/{bot_username}?start=dmnow")])
    if SUGGESTIONS_URL:
        rows.append([InlineKeyboardButton("💡 Suggestions", url=SUGGESTIONS_URL)])
    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="contact:anon")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)

def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="portal:home")]])

async def render_contact(client: Client, target_message: Message, edit: bool = True):
    me = await client.get_me()
    kb = _kb_contact(me.username)
    if edit:
        try:
            await target_message.edit_text(CONTACT_COPY, reply_markup=kb)
            return
        except Exception:
            pass
    await client.send_message(target_message.chat.id, CONTACT_COPY, reply_markup=kb)

def register(app: Client):

    # command (optional)
    @app.on_message(filters.private & filters.command(["contactadmins","contact","admins"]))
    async def cmd_contact(client: Client, m: Message):
        await render_contact(client, m.reply_to_message or m, edit=False)

    # open anon prompt
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        _PENDING_ANON.add(q.from_user.id)
        try:
            await q.message.edit_text(
                "🕵️ <b>Anonymous Message</b>\n"
                "Send me the message now (text only). I’ll forward it anonymously to the owner.",
                reply_markup=_kb_back()
            )
        except Exception:
            await q.message.reply_text(
                "🕵️ <b>Anonymous Message</b>\n"
                "Send me the message now (text only). I’ll forward it anonymously to the owner.",
                reply_markup=_kb_back()
            )
        await q.answer()

    # collect anon text (next message)
    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        if m.from_user.id not in _PENDING_ANON:
            return
        if OWNER_ID <= 0:
            await m.reply_text("Owner is not configured.")
            _PENDING_ANON.discard(m.from_user.id)
            return
        try:
            await client.send_message(
                OWNER_ID,
                f"🕵️ Anonymous message:\n\n{m.text}"
            )
            await m.reply_text("✅ Sent anonymously.", reply_markup=_kb_back())
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await m.reply_text("❌ Couldn’t send right now.")
        finally:
            _PENDING_ANON.discard(m.from_user.id)

    log.info("contact_admins wired")
