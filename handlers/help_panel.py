# Help panel + Buyer Rules / Requirements / Game Rules + Models Elsewhere
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

BUYER_RULES_TEXT = os.getenv("RULES_TEXT", "No rules text set yet.")
BUYER_REQ_TEXT   = os.getenv("BUYER_REQUIREMENTS_TEXT", "No buyer requirements set yet.")
GAME_RULES_TEXT  = os.getenv("GAME_RULES_TEXT", "No game rules set yet.")

MODELS_LINKS_TEXT = os.getenv("MODELS_LINKS_TEXT", "All verified off-platform links for our models are collected here.")
MODELS_LINKS_URL  = os.getenv("MODELS_LINKS_URL", "")

def _help_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("‼️ Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("✨ Buyer Requirements", callback_data="help_requirements")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_games")],
        [InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")],
    ]
    return InlineKeyboardMarkup(rows)

def _back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Help", callback_data="open_help")]])

def _models_links_kb() -> InlineKeyboardMarkup:
    rows = []
    if MODELS_LINKS_URL:
        rows.append([InlineKeyboardButton("🔗 Open Links", url=MODELS_LINKS_URL)])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    # Hub → Help
    @app.on_callback_query(filters.regex(r"^open_help$"))
    async def open_help(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "❓ <b>Help</b>\nTap a button below, or ask an admin if you’re stuck.",
            reply_markup=_help_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Optional /help command
    @app.on_message(filters.command(["help"]))
    async def cmd_help(_, m: Message):
        await m.reply_text(
            "❓ <b>Help</b>\nTap a button below, or ask an admin if you’re stuck.",
            reply_markup=_help_kb(),
            disable_web_page_preview=True,
        )

    # Sections
    @app.on_callback_query(filters.regex(r"^help_rules$"))
    async def help_rules(_, cq: CallbackQuery):
        await cq.message.edit_text(f"‼️ <b>Buyer Rules</b>\n\n{BUYER_RULES_TEXT}", reply_markup=_back_to_help_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_requirements$"))
    async def help_reqs(_, cq: CallbackQuery):
        await cq.message.edit_text(f"✨ <b>Buyer Requirements</b>\n\n{BUYER_REQ_TEXT}", reply_markup=_back_to_help_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_games$"))
    async def help_games(_, cq: CallbackQuery):
        await cq.message.edit_text(f"🎲 <b>Game Rules</b>\n\n{GAME_RULES_TEXT}", reply_markup=_back_to_help_kb(), disable_web_page_preview=True)
        await cq.answer()

    # “Find Our Models Elsewhere” hub button
    @app.on_callback_query(filters.regex(r"^open_models_links$"))
    async def open_models_links(_, cq: CallbackQuery):
        await cq.message.edit_text(
            f"✨ <b>Find Our Models Elsewhere</b>\n\n{MODELS_LINKS_TEXT}",
            reply_markup=_models_links_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()
