# handlers/contact_admins.py
# Contact Roni / Ruby + Suggestions + Anonymous message to OWNER_ID
# - Cute copy
# - Buttons that open on both Desktop & Mobile
# - Edits in-place (no duplicate blocks)
# - HTML formatting everywhere

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified

log = logging.getLogger("contact_admins")

def _to_int(s: str | None) -> int | None:
    try:
        return int(s) if s and s.isdigit() else None
    except Exception:
        return None

OWNER_ID        = _to_int(os.getenv("OWNER_ID"))
RONI_ID         = _to_int(os.getenv("RONI_ID"))
RUBY_ID         = _to_int(os.getenv("RUBY_ID"))
RONI_USERNAME   = (os.getenv("RONI_USERNAME") or "").lstrip("@")
RUBY_USERNAME   = (os.getenv("RUBY_USERNAME") or "").lstrip("@")
RONI_NAME       = os.getenv("RONI_NAME", "Roni")
RUBY_NAME       = os.getenv("RUBY_NAME", "Ruby")
SUGGESTIONS_URL = os.getenv("SUGGESTIONS_URL", "")  # optional link

BTN_BACK = "⬅️ Back to Main"

# Pending anonymous senders
_PENDING_ANON: set[int] = set()

COPY_CONTACT = (
    "👑 <b>Contact Admins</b>\n\n"
    "Need a hand, sweetness? You can DM an admin directly, or send an anonymous whisper that only the owner sees.\n\n"
    "<i>If the buttons don’t open, tap a name below:</i>\n"
    "{mentions}"
)

COPY_ANON = (
    "🕵️ <b>Anonymous Message</b>\n"
    "Type your message now (text only). I’ll deliver it secretly to the owner. 💌"
)

def _dm_url(user_id: int | None, username: str | None) -> str | None:
    """
    Prefer https://t.me/<username> (works everywhere).
    Fall back to tg://user?id=<id> if no username.
    """
    if username:
        return f"https://t.me/{username}"
    if user_id:
        return f"tg://user?id={user_id}"
    return None

def _mention_html(user_id: int | None, name: str, username: str | None) -> str:
    if username:
        return f'<a href="https://t.me/{username}">{name}</a>'
    if user_id:
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    return name

def _kb_contact() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    roni_link = _dm_url(RONI_ID, RONI_USERNAME)
    ruby_link = _dm_url(RUBY_ID, RUBY_USERNAME)

    if roni_link:
        rows.append([InlineKeyboardButton(f"👑 Message {RONI_NAME}", url=roni_link)])
    if ruby_link:
        rows.append([InlineKeyboardButton(f"👑 Message {RUBY_NAME}", url=ruby_link)])

    if SUGGESTIONS_URL:
        rows.append([InlineKeyboardButton("💡 Suggestions", url=SUGGESTIONS_URL)])

    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="contact:anon")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="home:main")])
    return InlineKeyboardMarkup(rows)

def _kb_back_only() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="home:main")]])

def _mentions_block() -> str:
    parts = []
    if (RONI_ID or RONI_USERNAME):
        parts.append(_mention_html(RONI_ID, RONI_NAME, RONI_USERNAME))
    if (RUBY_ID or RUBY_USERNAME):
        parts.append(_mention_html(RUBY_ID, RUBY_NAME, RUBY_USERNAME))
    return " • ".join(parts) if parts else "<i>(no admin mentions configured)</i>"

def register(app: Client):

    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_contact(client: Client, q: CallbackQuery):
        html = COPY_CONTACT.format(mentions=_mentions_block())
        try:
            await q.message.edit_text(
                html,
                reply_markup=_kb_contact(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except MessageNotModified:
            # Same text — just refresh the keyboard to avoid duplicates
            try:
                await q.message.edit_reply_markup(_kb_contact())
            except Exception:
                pass
        except Exception:
            # As a last resort, DO NOT send a new message (prevents duplicates)
            pass
        await q.answer()

    @app.on_message(filters.private & filters.command(["contactadmins", "contact", "admins"]))
    async def cmd_contact(client: Client, m: Message):
        html = COPY_CONTACT.format(mentions=_mentions_block())
        await client.send_message(
            m.chat.id,
            html,
            reply_markup=_kb_contact(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        if q.from_user:
            _PENDING_ANON.add(q.from_user.id)
        try:
            await q.message.edit_text(
                COPY_ANON,
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except MessageNotModified:
            try:
                await q.message.edit_reply_markup(_kb_back_only())
            except Exception:
                pass
        except Exception:
            pass
        await q.answer()

    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        if uid not in _PENDING_ANON:
            return

        if not OWNER_ID:
            await client.send_message(
                m.chat.id,
                "Owner is not configured.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
            )
            _PENDING_ANON.discard(uid)
            return

        try:
            await client.send_message(OWNER_ID, f"🕵️ Anonymous message:\n\n{m.text}", parse_mode=ParseMode.HTML)
            await client.send_message(
                m.chat.id,
                "✅ Sent anonymously. I’ll pass it along with a wink. 😉",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await client.send_message(
                m.chat.id,
                "❌ I couldn’t send that right now. Try again in a moment.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
            )
        finally:
            _PENDING_ANON.discard(uid)

    log.info("contact_admins wired (pretty copy, solid links, no duplicates)")
