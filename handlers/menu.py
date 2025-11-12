# handlers/menu.py
# Inline menu browser: /menus -> buttons of model names -> tap to view saved menu
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from utils.menu_store import store

log = logging.getLogger(__name__)

LIST_CB    = "menus:list"
OPEN_CB    = "menus:open"
SHOW_CB_P  = "menus:show:"  # prefix: menus:show:<Name>

def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _resolve_name(query: str) -> str:
    """
    Map any user-typed name (any case/quotes/extra spaces) to the exact stored key.
    Falls back to cleaned input if we don't find a match.
    """
    q = _clean(query)
    names = store.list_names() or []
    by_lower = {n.lower(): n for n in names}
    return by_lower.get(q.lower(), q)

def _names_keyboard() -> InlineKeyboardMarkup:
    names = store.list_names() or []
    if not names:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Create a menu with /createmenu", callback_data=LIST_CB)]]
        )
    # Sort for a stable, nice list
    names = sorted(names, key=lambda s: s.lower())
    rows = [[InlineKeyboardButton(n, callback_data=f"{SHOW_CB_P}{n}")] for n in names]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)])
    return InlineKeyboardMarkup(rows)

def _send_menu_text(msg_or_cq_message, name: str, text: str, as_edit: bool = True):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)]])
    content = f"<b>{name} — Menu</b>\n\n{text}"
    if as_edit:
        return msg_or_cq_message.edit_text(content, reply_markup=kb, disable_web_page_preview=True)
    return msg_or_cq_message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)

def register(app):
    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

    # List all menus
    @app.on_message(filters.command("menus"))
    async def menus_cmd(_, m: Message):
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_names_keyboard())

    # Direct open: /menu <Name>  (kept in THIS handler; no new files)
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            # No name → show picker
            return await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_names_keyboard())
        name = _resolve_name(parts[1])
        # Try fetching with multiple fallbacks (handles stores that normalize to lower)
        text = store.get_menu(name)
        if text is None:
            text = store.get_menu(name.lower())
        if text is None:
            text = store.get_menu(_clean(name))
        if text is None:
            return await m.reply_text(f"❌ No menu saved for <b>{name}</b>.\nUse /createmenu {name} <text…>")
        await _send_menu_text(m, name, text, as_edit=False)

    # Legacy: /showmenu <Name>
    @app.on_message(filters.command("showmenu"))
    async def show_menu_cmd(_, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            return await m.reply_text("Usage: /showmenu <Name>")
        name = _resolve_name(tokens[1])
        text = store.get_menu(name) or store.get_menu(name.lower()) or store.get_menu(_clean(name))
        if text is None:
            return await m.reply_text(f"❌ Menu '<b>{name}</b>' not found.")
        await _send_menu_text(m, name, text, as_edit=False)

    # Open/refresh the list from inline buttons
    @app.on_callback_query(filters.regex(f"^{OPEN_CB}$|^{LIST_CB}$"))
    async def list_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_names_keyboard())
        except Exception:
            await cq.answer()
            await cq.message.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_names_keyboard())

    # Tap on a specific name in the list
    @app.on_callback_query(filters.regex(r"^menus:show:.+"))
    async def show_cb(_, cq: CallbackQuery):
        raw = cq.data[len(SHOW_CB_P):]
        name = _resolve_name(raw)
        text = store.get_menu(name) or store.get_menu(name.lower()) or store.get_menu(_clean(name))
        if text is None:
            return await cq.answer(f"No menu saved for {name}.", show_alert=True)
        try:
            await _send_menu_text(cq.message, name, text, as_edit=True)
        except Exception:
            await cq.answer()
            await cq.message.reply_text(f"<b>{name} — Menu</b>\n\n{text}",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)]]),
                                        disable_web_page_preview=True)
