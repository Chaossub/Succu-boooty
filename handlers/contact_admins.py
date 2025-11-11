# handlers/contact_admins.py
# Contact Roni / Ruby + Suggestions + Anonymous message to OWNER_ID.
# - Buttons: DM Roni / DM Ruby (by ID or @username)
# - Pretty Markdown text (matches your other panels)
# - "Back to Main" returns via home:main

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

CONTACT_COPY = (
    "👑 **Contact Admins**\n\n"
    "• Tap a button below to DM an admin\n"
    "• Or send an anonymous message via the bot (goes to the owner only)."
)

def _dm_url(user_id: int | None, username: str | None) -> str | None:
    # Prefer numeric ID (tg:// link opens the user directly in Telegram apps).
    if user_id:
        return f"tg://user?id={user_id}"
    if username:
        return f"https://t.me/{username}"
    return None

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

async def render_contact(client: Client, target_message: Message, edit: bool = True):
    if edit:
        try:
            await target_message.edit_text(
                CONTACT_COPY,
                reply_markup=_kb_contact(),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            return
        except Exception:
            pass
    await client.send_message(
        target_message.chat.id,
        CONTACT_COPY,
        reply_markup=_kb_contact(),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )

def register(app: Client):

    # Open from the Home panel button
    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_contact(client: Client, q: CallbackQuery):
        try:
            await q.message.edit_text(
                CONTACT_COPY,
                reply_markup=_kb_contact(),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        finally:
            await q.answer()

    # Optional commands
    @app.on_message(filters.private & filters.command(["contactadmins","contact","admins"]))
    async def cmd_contact(client: Client, m: Message):
        await render_contact(client, m.reply_to_message or m, edit=False)

    # Begin anonymous flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        if q.from_user:
            _PENDING_ANON.add(q.from_user.id)

        text = (
            "🕵️ **Anonymous Message**\n"
            "Send me the message now (text only). I’ll forward it anonymously to the owner."
        )
        try:
            await q.message.edit_text(
                text,
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
        finally:
            await q.answer()

    # Collect the next private text as the anonymous message
    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        if uid not in _PENDING_ANON:
            return

        if not OWNER_ID:
            await m.reply_text(
                "Owner is not configured.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.MARKDOWN,
            )
            _PENDING_ANON.discard(uid)
            return

        try:
            await client.send_message(
                OWNER_ID,
                f"🕵️ Anonymous message:\n\n{m.text}",
                parse_mode=ParseMode.MARKDOWN,
            )
            await m.reply_text(
                "✅ Sent anonymously.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await m.reply_text(
                "❌ Couldn’t send right now.",
                reply_markup=_kb_back_only(),
                parse_mode=ParseMode.MARKDOWN,
            )
        finally:
            _PENDING_ANON.discard(uid)

    log.info("contact_admins wired")
