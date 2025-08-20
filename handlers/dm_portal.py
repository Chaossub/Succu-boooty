# handlers/dm_portal.py
# /start portal (welcome) with buttons:
#  - 💕 Menu
#  - Contact Admins 👑
#  - 🔥 Find Our Models Elsewhere
#  - ❓ Help
#
# Also marks the user DM-ready (if ReqStore available).

import os
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Optional ReqStore to mark DM-ready
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    class _DummyStore:
        def is_dm_ready_global(self, uid: int) -> bool: return False
        def set_dm_ready_global(self, uid: int, ready: bool, by_admin: bool=False): pass
    _store = _DummyStore()

# IDs (for Contact Admins panel; actual logic lives in contact_admins.py)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
RUBY_ID  = int(os.getenv("RUBY_ID", "0"))

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

# ---------- Links panel content ----------
MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    "👑 <b>Roni Jane (Owner)</b>\n"
    "https://allmylinks.com/chaossub283\n\n"
    "💎 <b>Ruby Ransom (Co-Owner)</b>\n"
    "https://allmylinks.com/rubyransoms\n\n"
    "🍑 <b>Peachy Rin</b>\n"
    "https://allmylinks.com/peachybunsrin\n\n"
    "⚡ <b>Savage Savy</b>\n"
    "https://allmylinks.com/savannahxsavage"
)

def _portal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_home")]])

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Choose an option below:"
)

def register(app: Client):

    # /start — send portal & mark DM-ready
    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        try:
            if not _store.is_dm_ready_global(uid):
                _store.set_dm_ready_global(uid, True, by_admin=False)
        except Exception:
            pass

        try:
            await m.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        except Exception:
            await m.reply_text("Welcome!", reply_markup=_portal_kb())

    # Back to home/portal
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def on_home(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Open Menu (handled by handlers.menu but we route the click here)
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def open_menu_cb(client: Client, cq: CallbackQuery):
        # Defer to handlers.menu to render tabs
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menus are unavailable right now.", reply_markup=_back_home_kb())
        await cq.answer()

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
        kb = _back_home_kb()
        try:
            await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        await cq.answer()
