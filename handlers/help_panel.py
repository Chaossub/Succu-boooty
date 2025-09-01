# handlers/help_panel.py
# Help panel with Buyer Rules / Requirements / Game Rules.

import os
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

BTN_BACK = "⬅️ Back to Main"
BTN_BUYER_RULES = "‼️ Buyer Rules"
BTN_BUYER_REQS  = "✨ Buyer Requirements"
BTN_GAME_RULES  = "🎲 Game Rules"

BUYER_RULES = os.getenv("RULES_TEXT", "No rules text set.")
BUYER_REQS  = os.getenv("BUYER_REQ_TEXT", "No buyer requirements set.")
GAME_RULES  = os.getenv("GAME_RULES_TEXT", "No game rules set.")

HELP_INTRO = "❓ <b>Help</b>\nTap a button above, or ask an admin if you’re stuck."

def _kb_main() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(BTN_BUYER_RULES, callback_data="help:rules")],
        [InlineKeyboardButton(BTN_BUYER_REQS,  callback_data="help:reqs")],
        [InlineKeyboardButton(BTN_GAME_RULES,  callback_data="help:games")],
        [InlineKeyboardButton(BTN_BACK,        callback_data="portal:home")],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="portal:home")]])

async def render_help(client: Client, target_message: Message, edit: bool = True):
    if edit:
        try:
            await target_message.edit_text(HELP_INTRO, reply_markup=_kb_main())
            return
        except Exception:
            pass
    await client.send_message(target_message.chat.id, HELP_INTRO, reply_markup=_kb_main())

def register(app: Client):

    # /help (optional – same content)
    @app.on_message(filters.private & filters.command("help"))
    async def cmd_help(client: Client, m: Message):
        await m.reply_text(HELP_INTRO, reply_markup=_kb_main())

    @app.on_callback_query(filters.regex(r"^help:(rules|reqs|games)$"))
    async def help_pages(client: Client, q: CallbackQuery):
        kind = q.data.split(":",1)[1]
        text = HELP_INTRO
        if kind == "rules":
            text = f"‼️ <b>Buyer Rules</b>\n\n{BUYER_RULES}"
        elif kind == "reqs":
            text = f"✨ <b>Buyer Requirements</b>\n\n{BUYER_REQS}"
        elif kind == "games":
            text = f"🎲 <b>Game Rules</b>\n\n{GAME_RULES}"

        try:
            await q.message.edit_text(text, reply_markup=_kb_back(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(text, reply_markup=_kb_back(), disable_web_page_preview=True)
        await q.answer()
