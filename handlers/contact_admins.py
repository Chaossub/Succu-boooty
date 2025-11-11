# handlers/contact_admins.py
# Contact Roni / Ruby + Anonymous message to OWNER_ID

import os, logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from pyrogram.errors import MessageNotModified

log = logging.getLogger("contact_admins")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Prefer usernames; fall back to IDs if needed
RONI_USERNAME = (os.getenv("RONI_USERNAME", "") or "").lstrip("@")
RUBY_USERNAME = (os.getenv("RUBY_USERNAME", "") or "").lstrip("@")
RONI_ID = os.getenv("RONI_ID")
RUBY_ID = os.getenv("RUBY_ID")

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

# Small in-memory state for anonymous flow
_PENDING_ANON = set()

COPY_HEADER = (
    "👑 <b>Contact Admins</b>\n\n"
    "Need a hand, sweetness? You can DM an admin directly, or send an "
    "anonymous whisper that only the owner sees.\n\n"
    "<i>If the buttons don’t open a DM, tap a name below:</i>\n"
    f"• <a href='https://t.me/{RONI_USERNAME}'> {RONI_NAME}</a>  •  "
    f"<a href='https://t.me/{RUBY_USERNAME}'> {RUBY_NAME}</a>"
)

def _dm_url(username: str | None, id_str: str | None) -> str | None:
    if username:
        return f"https://t.me/{username}"
    if id_str and id_str.isdigit():
        return f"tg://user?id={id_str}"
    return None

def _kb_contact() -> InlineKeyboardMarkup:
    rows = []
    roni_url = _dm_url(RONI_USERNAME, RONI_ID)
    ruby_url = _dm_url(RUBY_USERNAME, RUBY_ID)

    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Message {RONI_NAME}", url=roni_url)])
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Message {RUBY_NAME}", url=ruby_url)])

    rows.append([InlineKeyboardButton("🕵️ Anonymous Message", callback_data="contact:anon")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="home:main")])
    return InlineKeyboardMarkup(rows)

def _kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="home:main")]])

async def _show_contact(client: Client, msg: Message, *, edit: bool) -> None:
    try:
        if edit:
            await msg.edit_text(COPY_HEADER, reply_markup=_kb_contact(), disable_web_page_preview=True)
        else:
            await client.send_message(msg.chat.id, COPY_HEADER, reply_markup=_kb_contact(), disable_web_page_preview=True)
    except MessageNotModified:
        # Ignore harmless Telegram error when content/markup is same
        pass

def register(app: Client):

    # Open panel from main buttons (callback) or command
    @app.on_callback_query(filters.regex(r"^contact_admins:open$"))
    async def open_panel_cb(client: Client, q: CallbackQuery):
        await _show_contact(client, q.message, edit=True)
        await q.answer()

    @app.on_message(filters.private & filters.command(["contactadmins", "contact", "admins"]))
    async def open_panel_cmd(client: Client, m: Message):
        await _show_contact(client, m, edit=False)

    # Anonymous flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def anon_begin(client: Client, q: CallbackQuery):
        _PENDING_ANON.add(q.from_user.id)
        try:
            await q.message.edit_text(
                "🕵️ <b>Anonymous Message</b>\n"
                "Send me the message now (text only). I’ll forward it anonymously to the owner.",
                reply_markup=_kb_back_main()
            )
        except MessageNotModified:
            pass
        await q.answer()

    @app.on_message(filters.private & filters.text)
    async def anon_collect(client: Client, m: Message):
        if m.from_user.id not in _PENDING_ANON:
            return
        if OWNER_ID <= 0:
            _PENDING_ANON.discard(m.from_user.id)
            return await m.reply_text("Owner is not configured.", reply_markup=_kb_back_main())

        try:
            await client.send_message(
                OWNER_ID,
                f"🕵️ <b>Anonymous message</b>\n\n{m.text}",
                disable_web_page_preview=True
            )
            await m.reply_text("✅ Sent anonymously. Thanks for the whisper! 💌", reply_markup=_kb_back_main())
        except Exception as e:
            log.warning("Anonymous forward failed: %s", e)
            await m.reply_text("❌ Couldn’t send right now.", reply_markup=_kb_back_main())
        finally:
            _PENDING_ANON.discard(m.from_user.id)
