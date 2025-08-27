# dm_foolproof.py (excerpt – full file if you need)
import os, logging
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

log = logging.getLogger("SuccuBot")

try:
    from req_store import ReqStore
    _store: Optional["ReqStore"] = ReqStore()
except Exception:
    _store = None

async def safe_edit_text(msg, text: str, **kwargs):
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        rm = kwargs.get("reply_markup")
        if rm is not None:
            try:
                return await msg.edit_reply_markup(rm)
            except MessageNotModified:
                pass
        safe_kwargs = {k: v for k, v in kwargs.items() if k != "reply_markup"}
        return await msg.reply_text(text, **safe_kwargs)

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, "
    "flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menu", callback_data="m:menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_open_admins")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_models_links")],
            [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
        ]
    )

def _mark_dm_ready(uid: int) -> bool:
    """Try multiple method names so we work with any ReqStore version."""
    if not _store or not uid:
        return False
    try:
        # prefer *_global if present
        if hasattr(_store, "is_dm_ready_global") and hasattr(_store, "set_dm_ready_global"):
            if not _store.is_dm_ready_global(uid):
                _store.set_dm_ready_global(uid, True, by_admin=False)
                return True
            return False
        # fallbacks
        if hasattr(_store, "is_dm_ready") and hasattr(_store, "set_dm_ready"):
            if not _store.is_dm_ready(uid):
                _store.set_dm_ready(uid, True)
                return True
            return False
    except Exception as e:
        log.warning(f"DM-ready mark failed for {uid}: {e}")
    return False

def register(app: Client):

    @app.on_message(filters.private & filters.command(["start"]))
    async def start_portal(client: Client, m: Message):
        log.info("PORTAL: dm_foolproof /start")
        marked = False
        try:
            if m.from_user:
                marked = _mark_dm_ready(m.from_user.id)
        except Exception:
            pass

        # Send the main portal
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

        # Optional confirmation toast/message like your screenshot
        if marked:
            name = m.from_user.first_name if m.from_user else "Someone"
            try:
                await m.reply_text(f"✅ DM-ready — {name} just opened the portal.")
            except Exception:
                pass

    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(client: Client, q: CallbackQuery):
        await q.answer()
        await safe_edit_text(q.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^m:menus$"))
    async def open_menus(client: Client, q: CallbackQuery):
        await q.answer()
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await safe_edit_text(q.message, menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await safe_edit_text(q.message, "Menus are unavailable right now. Please try again shortly.", reply_markup=kb_main(), disable_web_page_preview=True)
