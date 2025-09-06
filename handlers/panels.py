# handlers/panels.py
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("SuccuBot")
log.setLevel(logging.INFO)
log.info("✅ Wired: handlers.panels")

# --- callback keys (accept old aliases too) ---
MENU_KEYS   = ("menu", "main_menu", "home", "open_menu", "start_menu", "Menu", "MENU")
ADMINS_KEYS = ("admins", "contact_admins", "admin_contact", "contactAdmins", "ContactAdmins")
MODELS_KEYS = ("models", "find_models", "models_elsewhere", "find_our_models_elsewhere")
HELP_KEYS   = ("help", "show_help", "help_center", "Help", "HELP")

# --- keyboards ---
def kb_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menu")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]])

# --- safe editor (works for text or media captions) ---
async def edit_safely(message, text, reply_markup=None):
    try:
        if getattr(message, "text", None):
            await message.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        else:
            await message.edit_caption(text, reply_markup=reply_markup)
    except Exception as e:
        # If content hasn't changed, just ignore Telegram's MESSAGE_NOT_MODIFIED, etc.
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            log.warning(f"[panels] edit_safely warn: {e}")

# --- panels content (keep simple; swap in your existing strings if you like) ---
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
    "Links hub & socials go here. Replace this text with your real links list."
)

TXT_HELP = (
    "❓ **Help**\n"
    "Use /help for full command list, or tap Back to return to the main menu."
)

# --- handlers ---
@Client.on_callback_query(filters.regex("^(" + "|".join(MENU_KEYS) + r")$"))
async def cb_menu(app, q):
    await edit_safely(q.message, TXT_HOME, kb_home())
    await q.answer()  # acknowledge press

@Client.on_callback_query(filters.regex("^(" + "|".join(ADMINS_KEYS) + r")$"))
async def cb_admins(app, q):
    await edit_safely(q.message, TXT_ADMINS, kb_back_home())
    await q.answer()

@Client.on_callback_query(filters.regex("^(" + "|".join(MODELS_KEYS) + r")$"))
async def cb_models(app, q):
    await edit_safely(q.message, TXT_MODELS, kb_back_home())
    await q.answer()

@Client.on_callback_query(filters.regex("^(" + "|".join(HELP_KEYS) + r")$"))
async def cb_help(app, q):
    await edit_safely(q.message, TXT_HELP, kb_back_home())
    await q.answer()
