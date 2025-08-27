# handlers/menu.py

import os
from typing import Dict

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from pyrogram.errors import MessageNotModified
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

# ==========
# ENV / CONFIG
# ==========
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Model usernames for DM links (book buttons & Contact Models grid)
RONI_USERNAME = os.getenv("RONI_USERNAME", "RoniUsername")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "RubyUsername")
RIN_USERNAME  = os.getenv("RIN_USERNAME",  "RinUsername")
SAVY_USERNAME = os.getenv("SAVY_USERNAME", "SavyUsername")

# Model menu texts (displayed above Book/Tip)
MENU_RONI = os.getenv("MENU_RONI", "Roni’s menu goes here.")
MENU_RUBY = os.getenv("MENU_RUBY", "Ruby’s menu goes here.")
MENU_RIN  = os.getenv("MENU_RIN",  "Rin’s menu goes here.")
MENU_SAVY = os.getenv("MENU_SAVY", "Savy’s menu goes here.")

# Text blobs from ENV
FIND_MODELS_TEXT      = os.getenv("FIND_MODELS_TEXT", "Links & profiles for our models elsewhere.")
BUYER_RULES_TEXT      = os.getenv("BUYER_RULES_TEXT", "Buyer Rules are not set in ENV.")
BUYER_REQUIREMENTS_TX = os.getenv("BUYER_REQUIREMENTS_TEXT", "Buyer Requirements are not set in ENV.")
GAME_RULES_TEXT       = os.getenv("GAME_RULES_TEXT", "Game Rules are not set in ENV.")

# ==========
# CONSTANT TEXTS
# ==========
WELCOME_TEXT = (
    "🔥 Welcome to SuccuBot 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing."
)

# Commands (non-admin) shown in Help → Commands
COMMANDS_TEXT = (
    "🤖 **Member Commands**\n"
    "• /start – open the portal\n"
    "• /portal – open the portal\n"
    "• Use menus to browse models, book, and more."
)

# ==========
# STATE (for Anonymous / Suggestions flows)
# ==========
STATE_AWAITING: Dict[int, str] = {}  # user_id -> "anon" | "suggest"

# ==========
# CALLBACK DATA KEYS
# ==========
CB_MAIN           = "main"
CB_MENUS          = "menus"
CB_MODEL_RONI     = "model_roni"
CB_MODEL_RUBY     = "model_ruby"
CB_MODEL_RIN      = "model_rin"
CB_MODEL_SAVY     = "model_savy"
CB_CONTACT_MODELS = "contact_models"
CB_CONTACT_ADMINS = "contact_admins"
CB_FIND_ELSEWHERE = "find_elsewhere"
CB_HELP           = "help_menu"
CB_BUYER_RULES    = "buyer_rules"
CB_BUYER_REQS     = "buyer_reqs"
CB_GAME_RULES     = "game_rules"
CB_COMMANDS       = "commands"
CB_TIP_SOON       = "tip_soon"
CB_BACK_MAIN      = "back_main"
CB_BACK_MENUS     = "back_menus"
CB_ANON           = "anon"
CB_SUGGEST        = "suggest"

# ==========
# KEYBOARDS
# ==========

def _kb_main() -> InlineKeyboardMarkup:
    # Single column (one per row), as requested
    rows = [
        [InlineKeyboardButton("📜 Menus", callback_data=CB_MENUS)],
        [InlineKeyboardButton("🌐 Contact Our Models Elsewhere", callback_data=CB_FIND_ELSEWHERE)],
        [InlineKeyboardButton("🛠 Contact Admins", callback_data=CB_CONTACT_ADMINS)],
        [InlineKeyboardButton("❓ Help", callback_data=CB_HELP)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_menus() -> InlineKeyboardMarkup:
    # 2x2 models grid, then Contact Models, then Back to Main
    rows = [
        [InlineKeyboardButton("🍷 Roni", callback_data=CB_MODEL_RONI),
         InlineKeyboardButton("💎 Ruby", callback_data=CB_MODEL_RUBY)],
        [InlineKeyboardButton("🍑 Rin", callback_data=CB_MODEL_RIN),
         InlineKeyboardButton("🔥 Savy", callback_data=CB_MODEL_SAVY)],
        [InlineKeyboardButton("📞 Contact Models", callback_data=CB_CONTACT_MODELS)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_model_menu(model_name: str, username: str) -> InlineKeyboardMarkup:
    # Book (DM url), Tip (coming soon), Back to Menus
    rows = [
        [InlineKeyboardButton(f"📖 Book {model_name}", url=f"https://t.me/{username}")],
        [InlineKeyboardButton(f"💸 Tip {model_name} (Coming Soon)", callback_data=CB_TIP_SOON)],
        [InlineKeyboardButton("🔙 Back to Menus", callback_data=CB_BACK_MENUS)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_contact_models() -> InlineKeyboardMarkup:
    # 2x2 grid of DM links; Back to Main ONLY
    rows = [
        [InlineKeyboardButton("📩 Roni", url=f"https://t.me/{RONI_USERNAME}"),
         InlineKeyboardButton("📩 Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("📩 Rin",  url=f"https://t.me/{RIN_USERNAME}"),
         InlineKeyboardButton("📩 Savy", url=f"https://t.me/{SAVY_USERNAME}")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_contact_admins() -> InlineKeyboardMarkup:
    # 2x2 (Message Roni, Message Ruby) (Anonymous, Suggestions), then Back to Main
    rows = [
        [InlineKeyboardButton("📩 Message Roni", url=f"https://t.me/{RONI_USERNAME}"),
         InlineKeyboardButton("📩 Message Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("📢 Anonymous Message", callback_data=CB_ANON),
         InlineKeyboardButton("💡 Suggestions", callback_data=CB_SUGGEST)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_find_elsewhere() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)]
    ]
    return InlineKeyboardMarkup(rows)

def _kb_help_root() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📜 Buyer Rules", callback_data=CB_BUYER_RULES)],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data=CB_BUYER_REQS)],
        [InlineKeyboardButton("🎮 Game Rules", callback_data=CB_GAME_RULES)],
        [InlineKeyboardButton("🤖 Commands", callback_data=CB_COMMANDS)],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_BACK_MAIN)]])

def _kb_back_menus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menus", callback_data=CB_BACK_MENUS)]])

# ==========
# RENDER HELPERS WITH SAFE EDIT
# ==========

async def _safe_edit_text(msg_obj, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        await msg_obj.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except MessageNotModified:
        # Ignore harmless "not modified" errors to prevent loops/crashes
        pass

# ==========
# VIEW RENDERERS
# ==========

async def show_main_menu(m: Message | CallbackQuery):
    if isinstance(m, CallbackQuery):
        await _safe_edit_text(m.message, WELCOME_TEXT, _kb_main())
        await m.answer()
    else:
        await m.reply_text(WELCOME_TEXT, reply_markup=_kb_main(), disable_web_page_preview=True)

async def show_menus(q: CallbackQuery):
    await _safe_edit_text(q.message, "📜 Menus", _kb_menus())
    await q.answer()

async def show_model_menu(q: CallbackQuery, model: str):
    # route text + keyboard
    if model == "Roni":
        text = f"🍷 Roni’s Menu 🍷\n{MENU_RONI}"
        kb = _kb_model_menu("Roni", RONI_USERNAME)
    elif model == "Ruby":
        text = f"💎 Ruby’s Menu 💎\n{MENU_RUBY}"
        kb = _kb_model_menu("Ruby", RUBY_USERNAME)
    elif model == "Rin":
        text = f"🍑 Rin’s Menu 🍑\n{MENU_RIN}"
        kb = _kb_model_menu("Rin", RIN_USERNAME)
    else:
        text = f"🔥 Savy’s Menu 🔥\n{MENU_SAVY}"
        kb = _kb_model_menu("Savy", SAVY_USERNAME)

    await _safe_edit_text(q.message, text, kb)
    await q.answer()

async def show_contact_models(q: CallbackQuery):
    await _safe_edit_text(q.message, "📞 Contact Models", _kb_contact_models())
    await q.answer()

async def show_contact_admins(q: CallbackQuery):
    await _safe_edit_text(q.message, "🛠 Contact Admins", _kb_contact_admins())
    await q.answer()

async def show_find_elsewhere(q: CallbackQuery):
    await _safe_edit_text(q.message, f"🌐 Find Our Models Elsewhere\n\n{FIND_MODELS_TEXT}", _kb_find_elsewhere())
    await q.answer()

async def show_help_root(q: CallbackQuery):
    await _safe_edit_text(q.message, "❓ Help", _kb_help_root())
    await q.answer()

async def show_help_blob(q: CallbackQuery, which: str):
    if which == "rules":
        text = f"📜 Buyer Rules\n\n{BUYER_RULES_TEXT}"
    elif which == "reqs":
        text = f"✅ Buyer Requirements\n\n{BUYER_REQUIREMENTS_TX}"
    elif which == "games":
        text = f"🎮 Games & Extras\n\n{GAME_RULES_TEXT}"
    else:
        text = COMMANDS_TEXT

    await _safe_edit_text(q.message, text, _kb_back_main())
    await q.answer()

# ==========
# ANON / SUGGEST FLOWS
# ==========

async def start_anon(q: CallbackQuery):
    STATE_AWAITING[q.from_user.id] = "anon"
    await q.answer("Send me the anonymous message now. I’ll deliver it to the owner’s DMs.", show_alert=False)
    # Also update the panel to remind user what to do:
    await _safe_edit_text(q.message, "📢 Anonymous Message\n\nPlease send your anonymous message now. I’m listening…", _kb_back_main())

async def start_suggest(q: CallbackQuery):
    STATE_AWAITING[q.from_user.id] = "suggest"
    await q.answer("Send me your suggestion now. I’ll deliver it to the owner’s DMs.", show_alert=False)
    await _safe_edit_text(q.message, "💡 Suggestions\n\nPlease send your suggestion now. I’m listening…", _kb_back_main())

async def capture_user_message_and_forward(app, m: Message):
    user_id = m.from_user.id if m.from_user else 0
    mode = STATE_AWAITING.get(user_id)
    if not mode:
        return  # Not in anon/suggest flow; ignore here.

    title = "Anonymous Message" if mode == "anon" else "Suggestion"
    sender = m.from_user.mention if m.from_user else "Unknown"
    text = f"📥 {title} received\n\nFrom: {sender} (id: {user_id})\n\nMessage:\n{m.text or m.caption or ''}"

    if OWNER_ID:
        try:
            await app.send_message(OWNER_ID, text, disable_web_page_preview=True)
        except Exception:
            # swallow any DM errors to avoid breaking user flow
            pass

    try:
        await m.reply_text("✅ Got it. I’ve delivered your message to the owner’s DMs.", disable_web_page_preview=True, reply_markup=_kb_main())
    except Exception:
        pass

    # Clear state
    STATE_AWAITING.pop(user_id, None)

# ==========
# TIP PLACEHOLDER
# ==========

async def tip_soon(q: CallbackQuery):
    await q.answer("💸 Tips are coming soon!", show_alert=True)

# ==========
# PUBLIC REGISTER
# ==========

def register(app):
    """
    Wire up all handlers for menus & navigation.
    Call this once from main.py:  handlers.menu.register(app)
    """

    # /start and /portal -> Welcome + Main Menu (always)
    async def _start_portal_handler(client, message: Message):
        await show_main_menu(message)

    app.add_handler(MessageHandler(_start_portal_handler, filters.command(["start", "portal"]) & ~filters.edited))

    # Capture anon/suggest free-form messages
    async def _free_text_capture(client, message: Message):
        await capture_user_message_and_forward(app, message)

    app.add_handler(MessageHandler(_free_text_capture, filters.text & ~filters.command(["start", "portal"])))

    # Callback router
    async def _on_cb(client, q: CallbackQuery):
        data = q.data or ""
        if data in (CB_MAIN, CB_BACK_MAIN):
            await show_main_menu(q)
        elif data in (CB_MENUS, CB_BACK_MENUS):
            await show_menus(q)
        elif data == CB_MODEL_RONI:
            await show_model_menu(q, "Roni")
        elif data == CB_MODEL_RUBY:
            await show_model_menu(q, "Ruby")
        elif data == CB_MODEL_RIN:
            await show_model_menu(q, "Rin")
        elif data == CB_MODEL_SAVY:
            await show_model_menu(q, "Savy")
        elif data == CB_CONTACT_MODELS:
            await show_contact_models(q)
        elif data == CB_CONTACT_ADMINS:
            await show_contact_admins(q)
        elif data == CB_FIND_ELSEWHERE:
            await show_find_elsewhere(q)
        elif data == CB_HELP:
            await show_help_root(q)
        elif data == CB_BUYER_RULES:
            await show_help_blob(q, "rules")
        elif data == CB_BUYER_REQS:
            await show_help_blob(q, "reqs")
        elif data == CB_GAME_RULES:
            await show_help_blob(q, "games")
        elif data == CB_COMMANDS:
            await show_help_blob(q, "cmds")
        elif data == CB_TIP_SOON:
            await tip_soon(q)
        elif data == CB_ANON:
            await start_anon(q)
        elif data == CB_SUGGEST:
            await start_suggest(q)
        else:
            await q.answer()  # no-op

    app.add_handler(CallbackQueryHandler(_on_cb))
