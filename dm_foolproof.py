# dm_foolproof.py
import os
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

# mark/ping comes from unified DM-ready module
from handlers.dm_ready import mark_from_start

# ──────────────── Welcome text ────────────────
WELCOME_TEXT = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

# ──────────────── Home keyboard ────────────────
def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

# ──────────────── Safe edit helper ────────────────
async def _safe_edit(msg, text: str, **kwargs):
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        if "reply_markup" in kwargs:
            try:
                return await msg.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                return
        return

# ──────────────── Register ────────────────
def register(app: Client):

    # The ONLY /start handler in the bot
    @app.on_message(filters.command("start"))
    async def _start(c: Client, m):
        # mark DM-ready only in private chats (first time shows once + pings owner)
        if m.chat and m.chat.type == enums.ChatType.PRIVATE and m.from_user:
            await mark_from_start(c, m.from_user)

        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True,
        )
        # NOTE: No StopPropagation in Pyrogram v2 — duplicates are prevented by wiring only this /start.

    # Router for Back/Main buttons
    @app.on_callback_query(filters.regex(r"^home$"))
    async def _home(_: Client, q: CallbackQuery):
        await _safe_edit(
            q.message,
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True
        )
