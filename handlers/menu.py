# Inline menu browser: /menus -> buttons of model names -> tap to view saved menu
import logging
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from utils.menu_store import store

log = logging.getLogger(__name__)

LIST_CB   = "menus:list"
OPEN_CB   = "menus:open"
SHOW_CB_P = "menus:show:"   # prefix: menus:show:<Name>

REGISTERED = False  # guard against double import

def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _find_name_ci(target: str) -> str | None:
    """Return the display name that matches target, case-insensitive."""
    if not target:
        return None
    t = target.casefold()
    for n in store.list_names():
        if (n or "").casefold() == t:
            return n
    return None

def _get_menu_ci(name: str):
    """
    Try exact, then case-insensitive.
    Returns (display_name or None, text or None).
    """
    key = _clean(name)
    if not key:
        return None, None

    txt = store.get_menu(key)
    if txt is not None:
        return key, txt

    match = _find_name_ci(key)
    if match:
        txt = store.get_menu(match)
        if txt is not None:
            return match, txt

    return None, None

def _names_keyboard() -> InlineKeyboardMarkup:
    names = sorted(set(store.list_names()))  # belt-and-suspenders de-dupe
    if not names:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ create a menu with /createmenu", callback_data=LIST_CB)]]
        )
    rows = [[InlineKeyboardButton(n, callback_data=f"{SHOW_CB_P}{n}")]
            for n in names]
    rows.append([InlineKeyboardButton("⬅ back", callback_data=LIST_CB)])
    return InlineKeyboardMarkup(rows)

def register(app):
    global REGISTERED
    if REGISTERED:
        return
    REGISTERED = True

    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

    # /menus  -> list;  /menu -> alias
    @app.on_message(filters.command(["menus", "menu"]))
    async def menus_cmd(_, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        # support "/menu Name" to jump straight to a specific menu
        if len(tokens) == 2 and tokens[0].lstrip("/").lower() == "menu":
            raw = tokens[1]
            name, text = _get_menu_ci(raw)
            log.info("/menu: raw=%r -> key=%r found=%s", raw, name, text is not None)
            if text is None:
                return await m.reply_text(f"no menu saved for { _clean(raw) }.")
            return await m.reply_text(f"{name} — menu\n\n{text}", disable_web_page_preview=True)

        kb = _names_keyboard()
        await m.reply_text("📖 menus — tap a name to view", reply_markup=kb)

    # /showmenu Name
    @app.on_message(filters.command("showmenu"))
    async def show_menu_cmd(_, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            return await m.reply_text("usage: /showmenu Name")
        raw = tokens[1]
        name, text = _get_menu_ci(raw)
        log.info("/showmenu: raw=%r -> key=%r found=%s", raw, name, text is not None)
        if text is None:
            return await m.reply_text(f"menu '{_clean(raw)}' not found.")
        await m.reply_text(f"{name} — menu\n\n{text}", disable_web_page_preview=True)

    # open / refresh the list UI
    @app.on_callback_query(filters.regex(f"^{OPEN_CB}$|^{LIST_CB}$"))
    async def list_cb(_, cq: CallbackQuery):
        kb = _names_keyboard()
        try:
            await cq.message.edit_text("📖 menus — tap a name to view", reply_markup=kb)
        except Exception:
            await cq.answer()
            await cq.message.reply_text("📖 menus — tap a name to view", reply_markup=kb)

    # show from list button
    @app.on_callback_query(filters.regex(r"^menus:show:.+"))
    async def show_cb(_, cq: CallbackQuery):
        raw = cq.data[len(SHOW_CB_P):]
        name, text = _get_menu_ci(raw)
        log.info("menus:show: raw=%r -> key=%r found=%s", raw, name, text is not None)

        if text is None:
            return await cq.answer(f"no menu saved for {_clean(raw)}.", show_alert=True)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ back", callback_data=LIST_CB)]])
        content = f"{name} — menu\n\n{text}"
        try:
            await cq.message.edit_text(content, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.answer()
            await cq.message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)
