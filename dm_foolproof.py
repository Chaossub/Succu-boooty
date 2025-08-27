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

# Optional: DM-ready marker
try:
    from req_store import ReqStore
    _store: Optional["ReqStore"] = ReqStore()
except Exception:
    _store = None


# ── Safe edit helpers to avoid 400 MESSAGE_NOT_MODIFIED ───────────────────────
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

async def safe_edit_markup(msg, reply_markup):
    try:
        return await msg.edit_reply_markup(reply_markup)
    except MessageNotModified:
        return None


# ── Portal text ───────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, "
    "flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)


# ── Main keyboard (EXACT layout) ──────────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menu", callback_data="m:menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_open_admins")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_models_links")],
            [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
        ]
    )


# ── Register ──────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start — this is the ONLY portal
    @app.on_message(filters.private & filters.command(["start"]))
    async def start_portal(client: Client, m: Message):
        log.info("PORTAL: dm_foolproof /start")
        try:
            if _store and m.from_user:
                uid = m.from_user.id
                if not _store.is_dm_ready_global(uid):
                    _store.set_dm_ready_global(uid, True, by_admin=False)
        except Exception:
            pass

        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Back to Main (menus use "dmf_home")
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(client: Client, q: CallbackQuery):
        await q.answer()
        await safe_edit_text(q.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Menus (routes to the unified handlers.menu)
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
            await safe_edit_text(
                q.message,
                "Menus are unavailable right now. Please try again shortly.",
                reply_markup=kb_main(),
                disable_web_page_preview=True,
            )
