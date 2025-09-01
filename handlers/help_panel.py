# handlers/help_panel.py
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

RULES_TEXT       = os.getenv("RULES_TEXT", "No rules have been set yet.")
BUYER_REQS_TEXT  = os.getenv("BUYER_REQS_TEXT", "No buyer requirements have been set yet.")
GAME_RULES_TEXT  = os.getenv("GAME_RULES_TEXT", "No game rules available yet.")
FIND_TEXT        = os.getenv("FIND_TEXT", "All verified off-platform links for our models are collected here. Check pinned posts for updates.")

def _help_main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("‼️ Buyer Rules", callback_data="help_open_rules")],
        [InlineKeyboardButton("✨ Buyer Requirements", callback_data="help_open_reqs")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_open_games")],
        [InlineKeyboardButton(BTN_BACK, callback_data="dmf_main")],
    ]
    return InlineKeyboardMarkup(rows)

def register(app: Client):

    # Main HELP button from the portal
    @app.on_callback_query(filters.regex("^help_open_main$"))
    async def help_main(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(
            "❓ <b>Help</b>\n\nPick an option:",
            reply_markup=_help_main_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^help_open_rules$"))
    async def help_rules(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(f"‼️ <b>Buyer Rules</b>\n\n{RULES_TEXT}", reply_markup=_help_main_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^help_open_reqs$"))
    async def help_reqs(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(f"✨ <b>Buyer Requirements</b>\n\n{BUYER_REQS_TEXT}", reply_markup=_help_main_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^help_open_games$"))
    async def help_games(client: Client, cq: CallbackQuery):
        await cq.message.edit_text(f"🎲 <b>Game Rules</b>\n\n{GAME_RULES_TEXT}", reply_markup=_help_main_kb(), disable_web_page_preview=True)
        await cq.answer()

    # “Find Our Models Elsewhere” from main portal (kept here so it’s in the same help family)
    @app.on_callback_query(filters.regex("^help_open_links$"))
    async def help_links(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="dmf_main")]])
        await cq.message.edit_text(f"✨ <b>Find Our Models Elsewhere</b>\n\n{FIND_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
