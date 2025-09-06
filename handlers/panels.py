# handlers/panels.py
import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

# -------------------------
# Small utility helpers
# -------------------------

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

async def _safe_edit(msg, text: str, kb: InlineKeyboardMarkup):
    """Edit without raising when content hasn't changed."""
    try:
        await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        pass

# -------------------------
# ENV-driven content
# -------------------------

# Help text blocks (ENV)
HELP_REQS  = os.getenv("BUYER_REQUIREMENTS_TEXT") or "No buyer requirements set in ENV."
HELP_RULES = os.getenv("BUYER_RULES_TEXT")        or "No buyer rules set in ENV."
HELP_GAMES = os.getenv("GAME_RULES_TEXT")         or "No game rules set in ENV."
HELP_EXEMPT= os.getenv("EXEMPTIONS_TEXT")         or "No exemptions text set in ENV."

# Model names for the Menus page (ENV)
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

# Main welcome copy (unchanged)
WELCOME_LINE_1 = "🔥 Welcome to SuccuBot 🔥"
WELCOME_LINE_2 = (
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, "
    "flirty, and flowing."
)
WELCOME_HINT = "✨ Use the menu below to navigate!"

def _main_kb() -> InlineKeyboardMarkup:
    # Keep your original main buttons / order exactly
    return InlineKeyboardMarkup([
        [_btn("💕 Menu", "nav:menus")],
        [_btn("👑 Contact Admins", "nav:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "nav:find")],
        [_btn("❓ Help", "nav:help")],
    ])

def _menus_kb() -> InlineKeyboardMarkup:
    # Model names in the Menus tab
    rows = [
        [_btn(f"💞 {RONI_NAME}", "menu:roni"), _btn(f"💞 {RUBY_NAME}", "menu:ruby")],
        [_btn(f"💞 {RIN_NAME}",  "menu:rin"),  _btn(f"💞 {SAVY_NAME}", "menu:savy")],
        [_btn("⬅️ Back to Main", "nav:main")],
    ]
    return InlineKeyboardMarkup(rows)

def _help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("💋 Buyer Requirements", "nav:help:reqs")],
        [_btn("📜 Buyer Rules", "nav:help:rules")],
        [_btn("🎲 Game Rules", "nav:help:games")],
        [_btn("🛡️ Exemptions", "nav:help:exempt")],
        [_btn("⬅️ Back to Main", "nav:main")],
    ])

def _back_to_help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[ _btn("⬅️ Back to Help", "nav:help") ]])

# -------------------------
# Renderers (edit-in-place)
# -------------------------

async def render_main(msg):
    text = f"{WELCOME_LINE_1}\n{WELCOME_LINE_2}\n\n{WELCOME_HINT}"
    await _safe_edit(msg, text, _main_kb())

async def render_menus(msg):
    await _safe_edit(msg, "💕 **Menus**\nPick a model whose menu is saved.", _menus_kb())

async def render_help(msg):
    await _safe_edit(msg, "❓ **Help**\nPick a topic:", _help_kb())

async def render_help_requirements(msg):
    await _safe_edit(msg, HELP_REQS, _back_to_help_kb())

async def render_help_rules(msg):
    await _safe_edit(msg, HELP_RULES, _back_to_help_kb())

async def render_help_games(msg):
    await _safe_edit(msg, HELP_GAMES, _back_to_help_kb())

async def render_help_exemptions(msg):
    await _safe_edit(msg, HELP_EXEMPT, _back_to_help_kb())

# -------------------------
# Register callbacks (no changes to other areas)
# -------------------------

def register(app):
    # Main
    @app.on_callback_query(filters.regex(r"^nav:main$"))
    async def _go_main(_, cq):
        await render_main(cq.message)
        await cq.answer()

    # Menus (model list)
    @app.on_callback_query(filters.regex(r"^nav:menus$"))
    async def _go_menus(_, cq):
        await render_menus(cq.message)
        await cq.answer()

    # Help hub + subpages (ENV-driven)
    @app.on_callback_query(filters.regex(r"^nav:help$"))
    async def _go_help(_, cq):
        await render_help(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:help:reqs$"))
    async def _help_reqs(_, cq):
        await render_help_requirements(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:help:rules$"))
    async def _help_rules(_, cq):
        await render_help_rules(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:help:games$"))
    async def _help_games(_, cq):
        await render_help_games(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:help:exempt$"))
    async def _help_exempt(_, cq):
        await render_help_exemptions(cq.message)
        await cq.answer()

    # NOTE: The actual *show menu content* should already be implemented
    # in your existing menu handler listening to ^menu:(roni|ruby|rin|savy)$.
    # We do not reimplement it here by your request.
