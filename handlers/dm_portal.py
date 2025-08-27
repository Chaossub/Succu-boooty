# handlers/dm_portal.py — legacy shim (NO /start here)
from __future__ import annotations
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery
from pyrogram.errors import MessageNotModified

async def _safe_edit(msg, text, **kwargs):
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        if kwargs.get("reply_markup") is not None:
            try:
                return await msg.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                pass
    return None

def register(app: Client):
    """
    Legacy callback aliases ONLY.
    This module intentionally does NOT register /start or send any new messages.
    It forwards old callback_data values to the new handlers.
    """

    # Old -> Menus
    @app.on_callback_query(filters.regex(r"^(open_menu|portal:menus)$"))
    async def _legacy_open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await _safe_edit(
                cq.message,
                menu_tabs_text(),
                reply_markup=menu_tabs_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # Old -> Help
    @app.on_callback_query(filters.regex(r"^(open_help|portal:help)$"))
    async def _legacy_open_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await _safe_edit(
                cq.message,
                HELP_MENU_TEXT,
                reply_markup=_help_menu_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # Old -> Links
    @app.on_callback_query(filters.regex(r"^(open_links|portal:links)$"))
    async def _legacy_open_links(client: Client, cq: CallbackQuery):
        try:
            from dm_foolproof import MODELS_LINKS_TEXT, _back_home_kb
            await _safe_edit(
                cq.message,
                MODELS_LINKS_TEXT,
                reply_markup=_back_home_kb(),
                disable_web_page_preview=False,
            )
        except Exception:
            pass
        await cq.answer()

    # Old -> Contact Admins
    @app.on_callback_query(filters.regex(r"^(open_admins|portal:admins)$"))
    async def _legacy_open_admins(client: Client, cq: CallbackQuery):
        try:
            from handlers.contact_admins import CONTACT_TEXT, _kb_admins
            await _safe_edit(
                cq.message,
                CONTACT_TEXT,
                reply_markup=_kb_admins(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # Old -> Back to Start
    @app.on_callback_query(filters.regex(r"^(back_home|portal:home)$"))
    async def _legacy_back_home(client: Client, cq: CallbackQuery):
        try:
            from dm_foolproof import WELCOME_TEXT, kb_main
            await _safe_edit(
                cq.message,
                WELCOME_TEXT,
                reply_markup=kb_main(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()
