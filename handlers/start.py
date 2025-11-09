# handlers/start.py
from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


def _home_kb() -> InlineKeyboardMarkup:
    # These callback_data values must match what your panels.py listens for:
    #   "menus", "admins", "models", "help"
    rows = [
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("🔥 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    @app.on_message(filters.private & filters.command("start"))
    async def start_message(_: Client, m: Message):
        text = (
            "🔥 *Welcome to SuccuBot* 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep "
            "things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!"
        )
        await m.reply_text(
            text,
            reply_markup=_home_kb(),
            disable_web_page_preview=True,
        )
