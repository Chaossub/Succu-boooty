# handlers/panels.py
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import CallbackQueryHandler

log = logging.getLogger("SuccuBot")

# --- callback keys (accept old aliases too) ---
MENU_KEYS   = ("menu", "main_menu", "home", "open_menu", "start_menu", "Menu", "MENU")
ADMINS_KEYS = ("admins", "contact_admins", "admin_contact", "contactAdmins", "ContactAdmins")
MODELS_KEYS = ("models", "find_models", "models_elsewhere", "find_our_models_elsewhere")
HELP_KEYS   = ("help", "show_help", "help_center", "Help", "HELP")

# --- keyboards (labels match your screenshot) ---
def kb_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menu")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]])

# --- text blocks (swap with your own copy as needed) ---
TXT_HOME = (
    "🔥 Welcome to **SuccuBot** 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)
TXT_ADMINS = (
    "👑 **Contact Admins**\n"
    "• Roni Jane — @Chaossub283\n"
    "• Ruby Ransoms — (add handle)\n\n"
    "Need help with anything? Tap and DM."
)
TXT_MODELS = (
    "🔥 **Find Our Models Elsewhere**\n"
    "Links hub & socials go here."
)
TXT_HELP = (
    "❓ **Help**\n"
    "Use /help for the full command list, or tap Back to return to the main menu."
)

# --- safe editor (works for text messages or media captions) ---
async def _edit_safely(msg, text, reply_markup=None):
    try:
        if getattr(msg, "text", None):
            await msg.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        else:
            await msg.edit_caption(text, reply_markup=reply_markup)
    except Exception as e:
        # Ignore MESSAGE_NOT_MODIFIED; log others
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            log.warning(f"[panels] edit warn: {e}")

# --- handlers (defined as plain funcs; wired in register(app)) ---
async def _cb_menu(client, q):
    await _edit_safely(q.message, TXT_HOME, kb_home())
    await q.answer()

async def _cb_admins(client, q):
    await _edit_safely(q.message, TXT_ADMINS, kb_back_home())
    await q.answer()

async def _cb_models(client, q):
    await _edit_safely(q.message, TXT_MODELS, kb_back_home())
    await q.answer()

async def _cb_help(client, q):
    await _edit_safely(q.message, TXT_HELP, kb_back_home())
    await q.answer()

def register(app):
    """
    Called by main.wire(...). Adds callback handlers so inline buttons fire.
    """
    # Build regex filters that accept old/new keys so legacy buttons still work
    f_menu   = filters.regex("^(" + "|".join(MENU_KEYS)   + r")$")
    f_admins = filters.regex("^(" + "|".join(ADMINS_KEYS) + r")$")
    f_models = filters.regex("^(" + "|".join(MODELS_KEYS) + r")$")
    f_help   = filters.regex("^(" + "|".join(HELP_KEYS)   + r")$")

    app.add_handler(CallbackQueryHandler(_cb_menu,   f_menu))
    app.add_handler(CallbackQueryHandler(_cb_admins, f_admins))
    app.add_handler(CallbackQueryHandler(_cb_models, f_models))
    app.add_handler(CallbackQueryHandler(_cb_help,   f_help))

    log.info("✅ Wired: handlers.panels (register)")
