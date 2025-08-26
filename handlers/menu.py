# handlers/menu.py
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from pyrogram.errors import MessageNotModified
import os

# ========= ENV CONFIG =========
WELCOME_TEXT = os.getenv("WELCOME_TEXT", "👋 Welcome to Succubus Sanctuary!")
# "Find our models elsewhere" — plain text blob from ENV (NOT a URL)
MODELS_ELSEWHERE_TEXT = os.getenv("MODELS_ELSEWHERE_TEXT", "Our models elsewhere:\n- ...")

# Help Docs from ENV (plain text)
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT", "Buyer rules not set.")
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "Buyer requirements not set.")
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "Game rules not set.")
MEMBER_COMMANDS_TEXT = os.getenv("MEMBER_COMMANDS_TEXT", "Member commands not set.")

# DM links (usernames) for models/admins
RONI_USERNAME = os.getenv("RONI_USERNAME", "roni_username_here")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "ruby_username_here")
SAVY_USERNAME = os.getenv("SAVY_USERNAME", "savy_username_here")
RIN_USERNAME  = os.getenv("RIN_USERNAME",  "rin_username_here")

def _tg_link(username: str) -> str:
    u = (username or "").strip().lstrip("@")
    return f"https://t.me/{u}" if u else "https://t.me/"

# ========= KEYBOARDS =========
def _kb_main() -> InlineKeyboardMarkup:
    # Main Menu keeps the welcome message text visible
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Menus", callback_data="menus"),
             InlineKeyboardButton("🌐 Find Our Models Elsewhere", callback_data="find_elsewhere")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="contact_admins"),
             InlineKeyboardButton("🆘 Help", callback_data="help")],
        ]
    )

def _kb_menus() -> InlineKeyboardMarkup:
    # Model menu entries (2x2) + Contact Models + Back to Main (long single row)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Roni", callback_data="model_menu:roni"),
             InlineKeyboardButton("Ruby", callback_data="model_menu:ruby")],
            [InlineKeyboardButton("Savy", callback_data="model_menu:savy"),
             InlineKeyboardButton("Rin",  callback_data="model_menu:rin")],
            [InlineKeyboardButton("💌 Contact Models", callback_data="contact_models")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
    )

def _kb_contact_models() -> InlineKeyboardMarkup:
    # DM links 2x2, and ONLY Back to Main as requested
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Message Roni", url=_tg_link(RONI_USERNAME)),
             InlineKeyboardButton("Message Ruby", url=_tg_link(RUBY_USERNAME))],
            [InlineKeyboardButton("Message Savy", url=_tg_link(SAVY_USERNAME)),
             InlineKeyboardButton("Message Rin",  url=_tg_link(RIN_USERNAME))],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
    )

def _kb_contact_admins() -> InlineKeyboardMarkup:
    # 2x2 grid + single long Back to Main
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Message Roni", url=_tg_link(RONI_USERNAME)),
             InlineKeyboardButton("Message Ruby", url=_tg_link(RUBY_USERNAME))],
            [InlineKeyboardButton("Anonymous Msg", callback_data="admin_anon"),
             InlineKeyboardButton("Suggestions", callback_data="admin_suggest")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
    )

def _kb_help() -> InlineKeyboardMarkup:
    # 2x2 grid + Back to Main
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules"),
             InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_requirements")],
            [InlineKeyboardButton("💡 Member Commands", callback_data="help_member_cmds"),
             InlineKeyboardButton("🎲 Game Rules", callback_data="help_games")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
    )

def _kb_back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")]])

# ========= MESSAGE SENDING HELPERS =========
async def _safe_edit(message: Message, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except MessageNotModified:
        # Ignore harmless error when content/markup did not change
        pass

# ========= HANDLERS =========
async def _start(client: Client, m: Message):
    # Show welcome text + Main Menu
    await m.reply_text(WELCOME_TEXT, reply_markup=_kb_main(), disable_web_page_preview=True)

async def _menus(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "📋 Menus", _kb_menus())

async def _contact_models(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "💌 Contact Models", _kb_contact_models())

async def _contact_admins(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "👑 Contact Admins", _kb_contact_admins())

async def _help(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "🆘 Help", _kb_help())

async def _find_elsewhere(client: Client, q: CallbackQuery):
    await q.answer()
    # Use ENV text block, not an external URL
    await _safe_edit(q.message, MODELS_ELSEWHERE_TEXT, _kb_back_main())

# ----- Model Menus (not DMs) -----
async def _model_menu(client: Client, q: CallbackQuery, whom: str):
    await q.answer()
    title_map = {
        "roni": "Roni’s Menu",
        "ruby": "Ruby’s Menu",
        "savy": "Savy’s Menu",
        "rin":  "Rin’s Menu",
    }
    title = title_map.get(whom.lower(), "Model Menu")
    # Placeholder 2×2 layout + Back to Menus (we'll wire real per-model menus later)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Book Model", callback_data=f"book:{whom}"),
             InlineKeyboardButton("Tip", callback_data=f"tip:{whom}")],
            [InlineKeyboardButton("Specials", callback_data=f"specials:{whom}"),
             InlineKeyboardButton("Games", callback_data=f"games:{whom}")],
            [InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")],
        ]
    )
    await _safe_edit(q.message, title, kb)

# Placeholders (no-ops for now)
async def _placeholder(client: Client, q: CallbackQuery):
    await q.answer("Coming soon ✨ (we’ll wire menus after buttons are confirmed)")

# ----- Help content senders -----
async def _help_rules(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, BUYER_RULES_TEXT, _kb_back_main())

async def _help_requirements(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, BUYER_REQUIREMENTS_TEXT, _kb_back_main())

async def _help_member_cmds(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, MEMBER_COMMANDS_TEXT, _kb_back_main())

async def _help_games(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, GAME_RULES_TEXT, _kb_back_main())

# ----- Admin inbox placeholders -----
async def _admin_anon(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "✉️ Send me your anonymous message here.\n\n(Feature wiring next — placeholder.)", _kb_back_main())

async def _admin_suggest(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "💡 Send your suggestion.\n\n(Feature wiring next — placeholder.)", _kb_back_main())

# ----- Back to Main (keep the welcome text visible) -----
async def _back_main(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, WELCOME_TEXT, _kb_main())

# ========= REGISTRATION =========
def register(app: Client):
    # /start and /portal show welcome text + main keyboard
    app.add_handler(MessageHandler(_start, filters.command(["start", "portal"])))

    # Callback routes (use regex patterns)
    app.add_handler(CallbackQueryHandler(_menus,           filters.regex(r"^menus$")))
    app.add_handler(CallbackQueryHandler(_contact_models,  filters.regex(r"^contact_models$")))
    app.add_handler(CallbackQueryHandler(_contact_admins,  filters.regex(r"^contact_admins$")))
    app.add_handler(CallbackQueryHandler(_help,            filters.regex(r"^help$")))
    app.add_handler(CallbackQueryHandler(_find_elsewhere,  filters.regex(r"^find_elsewhere$")))
    app.add_handler(CallbackQueryHandler(_back_main,       filters.regex(r"^back_main$")))

    # Help content pages
    app.add_handler(CallbackQueryHandler(_help_rules,        filters.regex(r"^help_rules$")))
    app.add_handler(CallbackQueryHandler(_help_requirements, filters.regex(r"^help_requirements$")))
    app.add_handler(CallbackQueryHandler(_help_member_cmds,  filters.regex(r"^help_member_cmds$")))
    app.add_handler(CallbackQueryHandler(_help_games,        filters.regex(r"^help_games$")))

    # Admin placeholders
    app.add_handler(CallbackQueryHandler(_admin_anon,    filters.regex(r"^admin_anon$")))
    app.add_handler(CallbackQueryHandler(_admin_suggest, filters.regex(r"^admin_suggest$")))

    # Model menus
    app.add_handler(CallbackQueryHandler(lambda c, q: _model_menu(c, q, "roni"), filters.regex(r"^model_menu:roni$")))
    app.add_handler(CallbackQueryHandler(lambda c, q: _model_menu(c, q, "ruby"), filters.regex(r"^model_menu:ruby$")))
    app.add_handler(CallbackQueryHandler(lambda c, q: _model_menu(c, q, "savy"), filters.regex(r"^model_menu:savy$")))
    app.add_handler(CallbackQueryHandler(lambda c, q: _model_menu(c, q, "rin"),  filters.regex(r"^model_menu:rin$")))

    # Placeholder actions
    app.add_handler(CallbackQueryHandler(_placeholder, filters.regex(r"^(book:|tip:|specials:|games:).+")))
