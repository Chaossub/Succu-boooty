# handlers/help_panel.py
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

# ========= Text Sources (env) =========
# Primary names:
BUYER_RULES_TEXT        = os.getenv("BUYER_RULES_TEXT", "").strip()
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
GAME_RULES_TEXT         = os.getenv("GAME_RULES_TEXT", "").strip()

# Backward-compatible fallbacks (in case you already set these):
if not BUYER_RULES_TEXT:
    BUYER_RULES_TEXT = os.getenv("RULES_TEXT", "").strip()
if not BUYER_REQUIREMENTS_TEXT:
    BUYER_REQUIREMENTS_TEXT = os.getenv("REQUIREMENTS_TEXT", "").strip()
if not GAME_RULES_TEXT:
    GAME_RULES_TEXT = os.getenv("GAME_RULES", "").strip() or os.getenv("GAME_RULES_TEXT_FALLBACK", "").strip()

# Sensible defaults if envs are empty:
if not BUYER_RULES_TEXT:
    BUYER_RULES_TEXT = "<b>Buyer Rules</b>\n• Be respectful\n• No chargebacks\n• Follow platform ToS"
if not BUYER_REQUIREMENTS_TEXT:
    BUYER_REQUIREMENTS_TEXT = "<b>Buyer Requirements</b>\n• Must be 18+\n• Valid payment method\n• Read rules before purchase"
if not GAME_RULES_TEXT:
    GAME_RULES_TEXT = "<b>Game Rules</b>\n• No cheating\n• Follow host instructions\n• Have fun!"

# ========= Root (Help) =========
HELP_MENU_TEXT = (
    "<b>Help</b>\n"
    "Choose an option."
)

def _help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:buyer_rules")],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help:buyer_requirements")],
        [InlineKeyboardButton("🕹️ Game Rules", callback_data="help:game_rules")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")],
    ])

def _sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Help", callback_data="dmf_help")],
        [InlineKeyboardButton("🏠 Back to Main", callback_data="dmf_home")],
    ])

def register(app: Client):

    # Root: Help
    @app.on_callback_query(filters.regex(r"^dmf_help$"))
    async def help_root(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    # Buyer Rules
    @app.on_callback_query(filters.regex(r"^help:buyer_rules$"))
    async def help_rules(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(BUYER_RULES_TEXT, reply_markup=_sub_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    # Buyer Requirements
    @app.on_callback_query(filters.regex(r"^help:buyer_requirements$"))
    async def help_requirements(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(BUYER_REQUIREMENTS_TEXT, reply_markup=_sub_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    # Game Rules
    @app.on_callback_query(filters.regex(r"^help:game_rules$"))
    async def help_game(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(GAME_RULES_TEXT, reply_markup=_sub_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()
