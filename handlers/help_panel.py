# Help panel with Buyer Rules / Requirements / Game Rules / Exemptions
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

# Pull text from env (use your existing keys; fallbacks are short but safe)
BUYER_RULES_TEXT = os.getenv("RULES_TEXT") or "Buyer & House Rules are not configured yet."
BUYER_REQS_TEXT  = os.getenv("BUYER_REQUIREMENTS_TEXT") or "Buyer requirements are not configured yet."
GAME_RULES_TEXT  = os.getenv("GAME_RULES_TEXT") or "Game rules are not configured yet."
EXEMPTIONS_TEXT  = os.getenv("EXEMPTIONS_TEXT") or "Exemptions: one every 6 months unless specified otherwise."

def _main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💕 Menus", callback_data="open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="open_contact_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="open_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="open_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_help_home() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("‼️ Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("✨ Buyer Requirements", callback_data="help_requirements")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_games")],
        [InlineKeyboardButton("🧾 Exemptions", callback_data="help_exemptions")],
        [InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_back_to_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Help", callback_data="open_help")]])

def register(app: Client):
    @app.on_callback_query(filters.regex(r"^(open_help|help_open)$"))
    async def open_help(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "❓ <b>Help</b>\nPick a topic below.",
            reply_markup=_kb_help_home(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_rules$"))
    async def help_rules(_, cq: CallbackQuery):
        await cq.message.edit_text(f"‼️ <b>Buyer Rules</b>\n\n{BUYER_RULES_TEXT}", reply_markup=_kb_back_to_help(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_requirements$"))
    async def help_reqs(_, cq: CallbackQuery):
        await cq.message.edit_text(f"✨ <b>Buyer Requirements</b>\n\n{BUYER_REQS_TEXT}", reply_markup=_kb_back_to_help(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_games$"))
    async def help_games(_, cq: CallbackQuery):
        await cq.message.edit_text(f"🎲 <b>Game Rules</b>\n\n{GAME_RULES_TEXT}", reply_markup=_kb_back_to_help(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help_exemptions$"))
    async def help_exemptions(_, cq: CallbackQuery):
        await cq.message.edit_text(f"🧾 <b>Exemptions</b>\n\n{EXEMPTIONS_TEXT}", reply_markup=_kb_back_to_help(), disable_web_page_preview=True)
        await cq.answer()

    # Slash shortcut in case someone types /help
    @app.on_message(filters.command(["help"]) & ~filters.edited)
    async def cmd_help(_, m: Message):
        await m.reply_text("❓ <b>Help</b>\nPick a topic below.", reply_markup=_kb_help_home(), disable_web_page_preview=True)
