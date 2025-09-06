# handlers/panels.py
import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# === ENV DRIVEN BITS (unchanged behavior) =====================================
RONI_USERNAME = os.getenv("RONI_USERNAME", "").lstrip("@")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "").lstrip("@")

# If you also keep these texts in ENV, we read them; otherwise fall back.
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "🔥 Find Our Models Elsewhere")
HELP_TEXT_TITLE = os.getenv("HELP_TEXT_TITLE", "❓ Help")
MAIN_MENU_LABEL = os.getenv("MAIN_MENU_LABEL", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_LABEL", "👑 Contact Admins")
BACK_MAIN_LABEL = os.getenv("BACK_MAIN_LABEL", "⬅️ Back to Main")

# === TEXTS (the two-message welcome you asked to keep) ========================
def info_card_text() -> str:
    return (
        "😈 If you ever need to know exactly what I can do, "
        "just press the Help button and I’ll spill all my secrets... 💋"
    )

def main_welcome_text() -> str:
    return (
        "🔥 Welcome to SuccuBot 🔥\n"
        "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ Use the menu below to navigate!"
    )

# === KEYBOARDS ================================================================
def get_main_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(MAIN_MENU_LABEL, callback_data="nav:menu")],
            [InlineKeyboardButton(ADMINS_LABEL, callback_data="nav:admins")],
            [InlineKeyboardButton(FIND_MODELS_TEXT, callback_data="nav:models")],
            [InlineKeyboardButton(HELP_TEXT_TITLE, callback_data="nav:help")],
        ]
    )

def get_admins_panel() -> InlineKeyboardMarkup:
    rows = []
    # Contact Roni
    if RONI_USERNAME:
        rows.append([InlineKeyboardButton("✉️ Contact Roni", url=f"https://t.me/{RONI_USERNAME}")])
    else:
        rows.append([InlineKeyboardButton("✉️ Contact Roni (missing)", callback_data="noop")])
    # Contact Ruby
    if RUBY_USERNAME:
        rows.append([InlineKeyboardButton("✉️ Contact Ruby", url=f"https://t.me/{RUBY_USERNAME}")])
    else:
        rows.append([InlineKeyboardButton("✉️ Contact Ruby (missing)", callback_data="noop")])

    # Anonymous suggestions stays as a callback so you can reply from the bot
    rows.append([InlineKeyboardButton("🕵️ Anonymous Suggestions", callback_data="nav:anon")])
    rows.append([InlineKeyboardButton(BACK_MAIN_LABEL, callback_data="nav:main")])
    return InlineKeyboardMarkup(rows)

# Placeholder keyboards (leave your existing renderers/handlers for these).
def get_models_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BACK_MAIN_LABEL, callback_data="nav:main")]])

def get_help_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BACK_MAIN_LABEL, callback_data="nav:main")]])

def get_menu_panel() -> InlineKeyboardMarkup:
    # Your custom per-model menu UI lives elsewhere; this is the shell with a back button.
    return InlineKeyboardMarkup([[InlineKeyboardButton(BACK_MAIN_LABEL, callback_data="nav:main")]])

# === CALLBACK NAV (uses edit, so NO duplication) ==============================
def register(app):
    # Back to Main (edit the existing message; avoids duplicates)
    @app.on_callback_query(filters.regex(r"^nav:main$"))
    async def _go_main(c, cq):
        await cq.message.edit_text(
            main_welcome_text(),
            reply_markup=get_main_panel(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^nav:admins$"))
    async def _go_admins(c, cq):
        await cq.message.edit_text(
            "📬 Contact Admins\nChoose how you want to reach us:",
            reply_markup=get_admins_panel(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^nav:models$"))
    async def _go_models(c, cq):
        # Keep your original text for models here if you had one in ENV.
        await cq.message.edit_text(
            FIND_MODELS_TEXT,
            reply_markup=get_models_panel(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^nav:help$"))
    async def _go_help(c, cq):
        # Your full help text likely comes from ENV; keep the existing renderer if you have one.
        await cq.message.edit_text(
            HELP_TEXT_TITLE,
            reply_markup=get_help_panel(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^nav:menu$"))
    async def _go_menu(c, cq):
        # This just shows your menus container with a Back; your own menu module can replace the body.
        await cq.message.edit_text(
            "💕 Menus\nPick a model whose menu is saved.",
            reply_markup=get_menu_panel(),
            disable_web_page_preview=True,
        )

    # harmless no-op to swallow clicks if a username is missing
    @app.on_callback_query(filters.regex(r"^noop$"))
    async def _noop(c, cq):
        await cq.answer("Not configured.", show_alert=False)
