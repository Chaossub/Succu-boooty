# handlers/help_panel.py
# Restores the Help panel with Buyer Rules / Buyer Requirements / Game Rules.

import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# pull long texts from env (you can keep them in .env or change here)
RULES_TEXT = os.getenv("RULES_TEXT", "No rules text set.")
BUYER_REQ_TEXT = os.getenv("BUYER_REQ_TEXT", "No buyer requirements set.")
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "No game rules set.")

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("‼️ Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("✨ Buyer Requirements", callback_data="help_breq")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_game")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_start")],
    ])

async def _open_help(client: Client, chat_id: int, mid: int | None = None):
    text = "❓ <b>Help</b>\nPick a section below."
    if mid:
        await client.edit_message_text(chat_id, mid, text, reply_markup=_kb_help(), disable_web_page_preview=True)
    else:
        await client.send_message(chat_id, text, reply_markup=_kb_help(), disable_web_page_preview=True)

def register(app: Client):

    # open Help from your Start panel button
    @app.on_callback_query(filters.regex("^dmf_help$"))
    async def _open_from_menu(c: Client, q: CallbackQuery):
        await _open_help(c, q.message.chat.id, q.message.id)
        await q.answer()

    # optional slash alias in private
    @app.on_message(filters.private & filters.command(["help"]))
    async def _cmd(c: Client, m: Message):
        await _open_help(c, m.chat.id)

    # subpages
    @app.on_callback_query(filters.regex("^help_rules$"))
    async def _rules(c: Client, q: CallbackQuery):
        await c.edit_message_text(
            q.message.chat.id, q.message.id,
            f"‼️ <b>Buyer Rules</b>\n{RULES_TEXT}",
            reply_markup=_kb_help(), disable_web_page_preview=True
        )
        await q.answer()

    @app.on_callback_query(filters.regex("^help_breq$"))
    async def _breq(c: Client, q: CallbackQuery):
        await c.edit_message_text(
            q.message.chat.id, q.message.id,
            f"✨ <b>Buyer Requirements</b>\n{BUYER_REQ_TEXT}",
            reply_markup=_kb_help(), disable_web_page_preview=True
        )
        await q.answer()

    @app.on_callback_query(filters.regex("^help_game$"))
    async def _game(c: Client, q: CallbackQuery):
        await c.edit_message_text(
            q.message.chat.id, q.message.id,
            f"🎲 <b>Game Rules</b>\n{GAME_RULES_TEXT}",
            reply_markup=_kb_help(), disable_web_page_preview=True
        )
        await q.answer()
