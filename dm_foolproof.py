# dm_foolproof.py
import os
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import MessageNotModified

log = logging.getLogger("SuccuBot")

# Optional DM-ready store
try:
    from req_store import ReqStore
    _store: Optional["ReqStore"] = ReqStore()
except Exception:
    _store = None


# ── Safe edit helpers (NO new-message fallback) ───────────────────────────────
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
    return None


# ── Portal copy ───────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, "
    "flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)


# ── Main keyboard (exact 4 buttons, “Menus” with s) ──────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data="m:menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_open_admins")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_models_links")],
            [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
        ]
    )


# ── DM-ready helper ───────────────────────────────────────────────────────────
def _mark_dm_ready(uid: int) -> bool:
    if not _store or not uid:
        return False
    try:
        if hasattr(_store, "is_dm_ready_global") and hasattr(_store, "set_dm_ready_global"):
            if not _store.is_dm_ready_global(uid):
                _store.set_dm_ready_global(uid, True, by_admin=False)
                return True
            return False
        if hasattr(_store, "is_dm_ready") and hasattr(_store, "set_dm_ready"):
            if not _store.is_dm_ready(uid):
                _store.set_dm_ready(uid, True)
                return True
            return False
    except Exception as e:
        log.warning(f"DM-ready mark failed for {uid}: {e}")
    return False


# ── Links panel text ─────────────────────────────────────────────────────────
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


# ── Register ──────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start — the ONLY portal
    @app.on_message(filters.private & filters.command(["start"]))
    async def start_portal(client: Client, m: Message):
        log.info("PORTAL: dm_foolproof /start")
        marked = False
        try:
            if m.from_user:
                marked = _mark_dm_ready(m.from_user.id)
        except Exception:
            pass

        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

        if marked:
            name = m.from_user.first_name if m.from_user else "Someone"
            try:
                await m.reply_text(f"✅ DM-ready — {name} just opened the portal.")
            except Exception:
                pass

    # Back to Main
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(client: Client, q: CallbackQuery):
        await q.answer()
        await safe_edit_text(q.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Menus
    @app.on_callback_query(filters.regex(r"^m:menus$"))
    async def open_menus(client: Client, q: CallbackQuery):
        await q.answer()
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await safe_edit_text(
                q.message,
                menu_tabs_text(),
                reply_markup=menu_tabs_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    # Links panel
    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def open_links(client: Client, q: CallbackQuery):
        await q.answer()
        await safe_edit_text(q.message, MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)

    # Help root
    @app.on_callback_query(filters.regex(r"^dmf_help$"))
    async def open_help(client: Client, q: CallbackQuery):
        await q.answer()
        try:
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await safe_edit_text(q.message, HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception:
            await safe_edit_text(q.message, "<b>Help</b>\nChoose an option.", reply_markup=_back_home_kb(), disable_web_page_preview=True)
