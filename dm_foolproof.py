# dm_foolproof.py
# Single /start entrypoint & main portal (marks DM-ready always).

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

log = logging.getLogger("dm_foolproof")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

MODELS_LINKS_TEXT = os.getenv("FIND_MODELS_TEXT") or (
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here."
)

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

def _set_dm_ready(uid: int) -> bool:
    """
    Always marks DM-ready. Uses req_store if available,
    but still sends group announce if not.
    """
    changed = True
    if _store:
        try:
            if hasattr(_store, "is_dm_ready_global"):
                if not _store.is_dm_ready_global(uid):
                    _store.set_dm_ready_global(uid, True, by_admin=False)
                else:
                    changed = False
            elif hasattr(_store, "is_dm_ready"):
                if not _store.is_dm_ready(uid):
                    _store.set_dm_ready(uid, True)
                else:
                    changed = False
        except Exception as e:
            log.warning(f"req_store failed: {e}")
    return changed

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="dmf_open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")]])

async def _safe_edit(message, text, **kwargs):
    try:
        return await message.edit_text(text, **kwargs)
    except MessageNotModified:
        if kwargs.get("reply_markup") is not None:
            try:
                return await message.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                pass
    return None

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_private(client: Client, m: Message):
        uid = m.from_user.id
        if _set_dm_ready(uid):
            # Announce to sanctuary group(s)
            group_ids = os.getenv("SANCTUARY_GROUP_IDS", "").split(",")
            for gid in group_ids:
                gid = gid.strip()
                if not gid:
                    continue
                try:
                    await client.send_message(int(gid), f"✅ DM-ready — {m.from_user.first_name} just opened the portal.")
                except Exception:
                    pass
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    @app.on_message(~filters.private & filters.command("start"))
    async def start_group(client: Client, m: Message):
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("dmf_home"))
    async def cb_home(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("dmf_links"))
    async def cb_links(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Menus
    @app.on_callback_query(filters.regex("dmf_open_menus"))
    async def cb_menus(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await _safe_edit(cq.message, menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await _safe_edit(cq.message, "💕 <b>Menus</b>\nPick a model or contact the team.", reply_markup=_back_home_kb())
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("dmf_admins"))
    async def cb_admins(client: Client, cq: CallbackQuery):
        try:
            from handlers.contact_admins import CONTACT_TEXT, _kb_admins
            await _safe_edit(cq.message, CONTACT_TEXT, reply_markup=_kb_admins(), disable_web_page_preview=True)
        except Exception:
            await _safe_edit(cq.message, "👑 <b>Contact Admins</b>\nNo admins configured.", reply_markup=_back_home_kb())
        await cq.answer()

    # Help
    @app.on_callback_query(filters.regex("dmf_help"))
    async def cb_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await _safe_edit(cq.message, HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception:
            await _safe_edit(cq.message, "❓ <b>Help</b>\nCommands not configured.", reply_markup=_back_home_kb())
        await cq.answer()
