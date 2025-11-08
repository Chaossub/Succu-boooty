# dm_foolproof.py
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified
from handlers.dm_ready import mark_from_start

WELCOME_TEXT = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
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

def register(app: Client):

    @app.on_message(filters.command("start"))
    async def _start(c: Client, m):
        if m.chat and m.chat.type == enums.ChatType.PRIVATE and m.from_user:
            await mark_from_start(c, m.from_user)

        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^home$"))
    async def _home(_: Client, q: CallbackQuery):
        await _safe_edit(
            q.message,
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True
        )
