# Inline menu browser: /menus -> buttons of model names -> tap to view saved menu
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from utils.menu_store import store

log = logging.getLogger(__name__)

LIST_CB   = "menus:list"
OPEN_CB   = "menus:open"
SHOW_CB_P = "menus:show:"   # prefix: menus:show:<Name>

def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _find_name_ci(target: str) -> str | None:
    """Return stored display name matching target (case-insensitive, ws-normalized)."""
    t = (target or "").casefold().replace("\u00A0", " ").strip()
    for n in store.list_names():
        if (n or "").replace("\u00A0", " ").strip().casefold() == t:
            return n
    return None

def _get_menu_ci(name: str) -> tuple[str | None, str | None]:
    """
    Try exact key, then case-insensitive display match.
    Returns (display_name, text) or (None, None).
    """
    key = _clean(name)
    if not key:
        return None, None

    txt = store.get_menu(key)
    if txt is not None:
        pretty = _find_name_ci(key) or key
        return pretty, txt

    match = _find_name_ci(key)
    if match:
        txt = store.get_menu(match)
        if txt is not None:
            return match, txt

    return None, None

def _names_keyboard() -> InlineKeyboardMarkup:
    names = store.list_names()
    if not names:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Create a menu with /createmenu", callback_data=LIST_CB)]]
        )
    rows: list[list[InlineKeyboardButton]] = []
    for n in names:
        rows.append([InlineKeyboardButton(n, callback_data=f"{SHOW_CB_P}{n}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

    @app.on_message(filters.command("menus"))
    async def menus_cmd(_: Client, m: Message):
        kb = _names_keyboard()
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    @app.on_message(filters.command("showmenu"))
    async def show_menu_cmd(_: Client, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            await m.reply("Usage: /showmenu <Name>")
            return
        raw = tokens[1]
        name, text = _get_menu_ci(raw)
        log.info("showmenu: raw=%r -> key=%r found=%s", raw, name, text is not None)
        if text is None:
            await m.reply(f"Menu '<b>{_clean(raw)}</b>' not found.")
            return
        await m.reply(text, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(f"^{OPEN_CB}$|^{LIST_CB}$"))
    async def list_cb(_: Client, cq: CallbackQuery):
        kb = _names_keyboard()
        try:
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)
        except Exception:
            await cq.answer()
            await cq.message.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    @app.on_callback_query(filters.regex(r"^menus:show:.+"))
    async def show_cb(_: Client, cq: CallbackQuery):
        raw = (cq.data or "")[len(SHOW_CB_P):]
        name, text = _get_menu_ci(raw)
        log.info("menus:show: raw=%r -> key=%r found=%s", raw, name, text is not None)

        if text is None:
            await cq.answer(f"No menu saved for {_clean(raw)}.", show_alert=True)
            return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)]])
        content = f"<b>{name} — Menu</b>\n\n{text}"
        try:
            await cq.message.edit_text(content, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.answer()
            await cq.message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)
