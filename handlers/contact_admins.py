# handlers/contact_admins.py
# Contact Roni / Ruby + Suggestions + Anonymous message to OWNER_ID.
# - Clean HTML styling (no raw tags shown)
# - DM buttons work with tg://openmessage?user_id=..., or fall back to @username links
# - Also prints inline profile mentions as an extra clickable fallback
# - Back to Main uses home:main, matching your panels

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from pyrogram.enums import ParseMode

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

# Small in-memory state for anonymous messages
_PENDING_ANON: set[int] = set()

CONTACT_COPY_HTML = (
    "👑 <b>Contact Admins</b>\n\n"
    "• Tap a button below to DM an admin\n"
    "• Or send an anonymous message via the bot (goes to the owner only).\n\n"
    "<i>If the buttons don’t open a DM, use these direct mentions:</i>\n"
    "{mentions}"
)

ANON_TEXT_HTML = (
    "🕵️ <b>Anonymous Message</b>\n"
    "Send me the message now (text only). I’ll forward it anonymously to the owner."
)

def _dm_button_url(user_id: int | None, username: str | None) -> str | None:
    """
    Prefer tg://openmessage?user_id=... (works better on many clients).
    If no id, fall back to https://t.me/<username>.
    """
    if user_id:
        return f"tg://openmessage?user_id={user_id}"
    if username:
        return f"https://t.me/{username}"
    return None

def _mention_html(user_id: int | None, name: str, username: str | None) -> str:
    """
    Inline HTML mention fallback. If user_id exists, use tg://user?id=…,
    else fall back to https://t.me/<username>. If neither exists, just show the name.
    """
    if user_id:
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    if username:
        return f'<a href="https://t.me/{username}">{name}</a>'
    return name

def _kb_contact() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    roni_link = _dm_button_url(RONI_ID, RONI_USERNAME)
    ruby_link = _dm_button_url(RUBY_ID, RUBY_USERNAME)

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

async def _send_or_edit(client: Client, msg: Message, html: str, kb: InlineKeyboardMarkup, edit: bool):
    if edit:
        try:
            await msg.edit_text(
                html,
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass
    await client.send_message(
        msg.chat.id,
        html,
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

def register(app: Client):

    # Open from the Home panel button
    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_contact(client: Client, q: CallbackQuery):
        mentions = " • " + " • ".join(
            x for x in [
                _mention_html(RONI_ID, RONI_NAME, RONI_USERNAME) if (RONI_ID or RONI_USERNAME) else None,
                _mention_html(RUBY_ID, RUBY_NAME, RUBY_USERNAME) if (RUBY_ID or RUBY_USERNAME) else None,
            ] if x
        ) if (RONI_ID or RONI_USERNAME or RUBY_ID or RUBY_USERNAME) else "<i>(no admin mentions configured)</i>"

        html = CONTACT_COPY_HTML.format(mentions=mentions)
        await _send_or_edit(client, q.message, html, _kb_contact(), edit=True)
        await q.answer()

    # Optional commands (private)
    @app.on_message(filters.private & filters.command(["contactadmins","contact","admins"]))
    async def cmd_contact(client: Client, m: Message):
        mentions = " • " + " • ".join(
            x for x in [
                _mention_html(RONI_ID, RONI_NAME, RONI_USERNAME) if (RONI_ID or RONI_USERNAME) else None,
                _mention_html(RUBY_ID, RUBY_NAME, RUBY_USERNAME) if (RUBY_ID or RUBY_USERNAME) else None,
            ] if x
        ) if (RONI_ID or RONI_USERNAME or RUBY_ID or RUBY_USERNAME) else "<i>(no admin mentions configured)</i>"

        html = CONTACT_COPY_HTML.format(mentions=mentions)
        await _send_or_edit(client, m, html, _kb_contact(), edit=False)

    # Begin anonymous flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        if q.from_user:
            _PENDING_ANON.add(q.from_user.id)
        await _send_or_edit(client, q.message, ANON_TEXT_HTML, _kb_back_only(), edit=True)
        await q.answer()

    # Collect the next private text as the anonymous message
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
            await client.send_message(
                OWNER_ID,
                f"🕵️ Anonymous message:\n\n{m.text}",
                parse_mode=ParseMode.HTML,
            )
            await client.send_message(
                m.chat.id,
                "✅ Sent anonymously.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await client.send_message(
                m.chat.id,
                "❌ Couldn’t send right now.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.HTML,
            )
        finally:
            _PENDING_ANON.discard(uid)

    log.info("contact_admins wired (HTML + reliable DM links)")
