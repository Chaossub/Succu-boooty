# handlers/dm_portal.py  (callbacks only; NO /start here)
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Text for the external links panel
MODELS_LINKS_TEXT = os.getenv("MODELS_LINKS_TEXT", "").strip() or (
    "<b>Find Our Models Elsewhere</b>\n\n"
    "• Roni — Instagram / Fans\n"
    "• Ruby — Instagram / Fans\n"
    "• Rin — Instagram / Fans\n"
    "• Savy — Instagram / Fans\n\n"
    "Ask an admin if you need a direct link."
)

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_home")]])

def register(app: Client):

    # Open Contact Admins (panel lives in handlers.contact_admins)
    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def open_admins_cb(client: Client, cq: CallbackQuery):
        try:
            from handlers.contact_admins import build_admins_kb, CONTACT_TEXT
            await cq.message.edit_text(CONTACT_TEXT, reply_markup=build_admins_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Contact panel is unavailable right now.", reply_markup=_back_home_kb())
        await cq.answer()

    # Links panel
    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def on_links(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Help root (actual help menu lives in handlers.help_panel)
    @app.on_callback_query(filters.regex(r"^dmf_help$"))
    async def on_help_root(client: Client, cq: CallbackQuery):
        # Just hand off; handlers.help_panel registers the real 'dmf_help' content
        try:
            from handlers.help_panel import _help_menu_kb, HELP_MENU_TEXT  # if exposed
            await cq.message.edit_text(HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception:
            # If help_panel handles its own 'dmf_help', it will edit this on its own
            pass
        await cq.answer()
