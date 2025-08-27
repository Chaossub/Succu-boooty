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
    """
    Edit the SAME message. If Telegram says content is identical, try editing only
    the keyboard. Do NOT send a new message — avoids duplicate 'Welcome' posts.
    """
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

async def safe_edit_markup(msg, reply_markup):
    try:
        return await msg.edit_reply_markup(reply_markup)
    except MessageNotModified:
        return None


# ── Portal copy ───────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, "
    "flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)


# ── Main keyboard (exact 4 buttons) ───────────────────────────────────────────
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
    """Mark user DM-ready (supports both *_global and non-global store APIs)."""
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


# ── Register ──────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start — the ONLY portal
    @app.on_message(filters.private & filters.command(["start"]))
    async def start_portal(client: Client, m: Message):
        log.info("PORTAL: dm_foolproof /start")

        # Mark DM-ready if possible
        marked = False
        try:
            if m.from_user:
                marked = _mark_dm_ready(m.from_user.id)
        except Exception:
            pass

        # Send the welcome ONCE
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

        # Post a single confirmation line (not another welcome)
        if marked:
            name = m.from_user.first_name if m.from_user else "Someone"
            try:
                await m.reply_text(f"✅ DM-ready — {name} just opened the portal.")
            except Exception:
                pass

    # Back to Main — edit the SAME message; never post a new one
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(client: Client, q: CallbackQuery):
        await q.answer()
        await safe_edit_text(q.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Menus — delegate to unified handlers.menu (edits the same message)
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
