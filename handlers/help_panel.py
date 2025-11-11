# handlers/help_panel.py
# Help panel with Buyer Requirements / Buyer Rules / Game Rules + Back.

import os
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

BTN_BACK         = "⬅ Back to Main"
BTN_BUYER_REQS   = "✨ Buyer Requirements"
BTN_BUYER_RULES  = "‼️ Buyer Rules"
BTN_GAME_RULES   = "🎲 Game Rules"

BUYER_REQUIREMENTS = os.getenv("BUYER_REQUIREMENTS_TEXT", "No buyer requirements set.")
BUYER_RULES        = os.getenv("BUYER_RULES_TEXT", "No buyer rules set.")
GAME_RULES         = os.getenv("GAME_RULES_TEXT", "No game rules set.")

HELP_INTRO = (
    "❓ Help\n"
    "Pick one below. If you’re still stuck, use Contact Admins 💌"
)

def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_BUYER_REQS,  callback_data="help:reqs")],
        [InlineKeyboardButton(BTN_BUYER_RULES, callback_data="help:rules")],
        [InlineKeyboardButton(BTN_GAME_RULES,  callback_data="help:games")],
        [InlineKeyboardButton(BTN_BACK,        callback_data="portal:home")],
    ])

def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="portal:home")]])

def register(app: Client):
    # Open the help panel from a button
    @app.on_callback_query(filters.regex(r"^help:open$"))
    async def _open_help(_, q: CallbackQuery):
        try:
            await q.message.edit_text(HELP_INTRO, reply_markup=_kb_main(), disable_web_page_preview=True)
        finally:
            await q.answer()

    # /help (optional)
    @app.on_message(filters.private & filters.command("help"))
    async def _cmd_help(_, m: Message):
        await m.reply_text(HELP_INTRO, reply_markup=_kb_main(), disable_web_page_preview=True)

    # Pages
    @app.on_callback_query(filters.regex(r"^help:(reqs|rules|games)$"))
    async def _pages(_, q: CallbackQuery):
        kind = q.data.split(":", 1)[1]
        if kind == "reqs":
            text = f"✨ Buyer Requirements\n\n{BUYER_REQUIREMENTS}"
        elif kind == "rules":
            text = f"‼️ Buyer Rules\n\n{BUYER_RULES}"
        else:
            text = f"🎲 Game Rules\n\n{GAME_RULES}"

        try:
            await q.message.edit_text(text, reply_markup=_kb_back(), disable_web_page_preview=True)
        finally:
            await q.answer()
