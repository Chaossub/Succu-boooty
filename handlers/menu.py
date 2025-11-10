# handlers/menu.py
# Inline menu browser: /menu → buttons of model names → tap to view saved menu
import logging
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
)
from utils.menu_store import store

log = logging.getLogger(__name__)

LIST_CB   = "menu:list"
SHOW_CB_P = "menu:show:"  # prefix: menu:show:<Name>

def _clean(name: str) -> str:
    # guard against invisible/odd chars pasted from UI
    return name.strip().strip("»«‘’“”\"'`").strip()

def _names_keyboard():
    names = store.list_names()
    if not names:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Create a menu with /createmenu", callback_data=LIST_CB)]]
        )
    rows = []
    for n in names:
        rows.append([InlineKeyboardButton(n, callback_data=f"{SHOW_CB_P}{n}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)])
    return InlineKeyboardMarkup(rows)

def register(app):
    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

    # /menu -> list names as buttons
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        kb = _names_keyboard()
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # optional alias
    @app.on_message(filters.command("menus"))
    async def menus_cmd(_, m: Message):
        kb = _names_keyboard()
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # show a specific menu via text command: /showmenu Name
    @app.on_message(filters.command("showmenu"))
    async def show_menu_cmd(_, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            return await m.reply("Usage: /showmenu <Name>")
        name = _clean(tokens[1])
        text = store.get_menu(name)
        if text is None:
            return await m.reply(f"Menu '<b>{name}</b>' not found.")
        await m.reply(text)

    # callback: list
    @app.on_callback_query(filters.regex(f"^{LIST_CB}$"))
    async def list_cb(_, cq: CallbackQuery):
        kb = _names_keyboard()
        try:
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)
        except Exception:
            await cq.answer()
            await cq.message.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # callback: show menu
    @app.on_callback_query(filters.regex(r"^menu:show:.+"))
    async def show_cb(_, cq: CallbackQuery):
        raw = cq.data[len(SHOW_CB_P):]
        name = _clean(raw)
        text = store.get_menu(name)
        if text is None:
            return await cq.answer(f"No menu saved for {name}.", show_alert=True)

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)]]
        )
        content = f"<b>{name} — Menu</b>\n\n{text}"
        try:
            await cq.message.edit_text(content, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.answer()
            await cq.message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)
