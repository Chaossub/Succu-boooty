# handlers/menu.py
# Inline menu browser: /menus -> buttons of model names -> tap to view saved menu
import logging
import os, re
from pyrogram import Client, filters
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

# ---------- contacts parsing (for 📖 Book) ----------
# MODELS_CONTACTS="Rin=@rin, Ruby=ruby123"
_CONTACTS: dict[str, str] = {}
_raw = os.getenv("MODELS_CONTACTS", "")
for part in _raw.split(","):
    s = part.strip()
    if not s:
        continue
    m = re.split(r"[:=]", s, maxsplit=1)
    if len(m) == 2:
        k, v = m[0].strip(), m[1].strip().lstrip("@")
        if k and v:
            _CONTACTS[k] = v

def _slug_env_key(name: str) -> str:
    # MODEL_USERNAME_<SLUG>
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name or "").upper().strip("_")
    return f"MODEL_USERNAME_{slug}"

def _username_for(name: str) -> str | None:
    # exact
    if name in _CONTACTS:
        return _CONTACTS[name]
    # case-insensitive
    t = (name or "").casefold()
    for k, v in _CONTACTS.items():
        if k.casefold() == t:
            return v
    # per-model env
    v = os.getenv(_slug_env_key(name), "").strip().lstrip("@")
    return v or None

# ---------- helpers ----------
def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _find_name_ci(target: str) -> str | None:
    """Return the actual stored name that matches target, case-insensitive."""
    if not target:
        return None
    t = target.casefold()
    for n in store.list_names():
        if (n or "").casefold() == t:
            return n
    return None

def _get_menu_ci(name: str) -> tuple[str | None, str | None]:
    """
    Try exact, then case-insensitive. Returns (actual_name, text).
    actual_name is the canonical stored key (for buttons/back labels).
    """
    key = _clean(name)
    if not key:
        return None, None

    # exact first
    txt = store.get_menu(key)
    if txt is not None:
        return key, txt

    # case-insensitive fallback
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

def _menu_keyboard(display_name: str) -> InlineKeyboardMarkup:
    """
    Keyboard shown on a model's menu:
    📖 Book (if username known), 💸 Tip (placeholder), ⬅️ Back, 🏠 Main
    """
    rows: list[list[InlineKeyboardButton]] = []
    uname = _username_for(display_name)
    first_row: list[InlineKeyboardButton] = []
    if uname:
        first_row.append(InlineKeyboardButton("📖 Book", url=f"https://t.me/{uname}"))
    first_row.append(InlineKeyboardButton("💸 Tip", callback_data=f"tip:{display_name}"))
    rows.append(first_row)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB)])
    rows.append([InlineKeyboardButton("🏠 Main", callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)

# ---------- registration ----------
def register(app: Client):
    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

    # Open / refresh the list UI
    @app.on_message(filters.command("menus"))
    async def menus_cmd(_, m: Message):
        kb = _names_keyboard()
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # Show a specific menu by command
    @app.on_message(filters.command("showmenu"))
    async def show_menu_cmd(_, m: Message):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            return await m.reply("Usage: /showmenu <Name>")
        raw = tokens[1]
        name, text = _get_menu_ci(raw)
        log.info("showmenu: raw=%r -> key=%r found=%s", raw, name, text is not None)
        if text is None:
            return await m.reply(f"Menu '<b>{_clean(raw)}</b>' not found.")
        await m.reply(
            f"<b>{name} — Menu</b>\n\n{text}",
            reply_markup=_menu_keyboard(name),
            disable_web_page_preview=True,
        )

    # Open list via callback
    @app.on_callback_query(filters.regex(f"^{OPEN_CB}$|^{LIST_CB}$"))
    async def list_cb(_, cq: CallbackQuery):
        kb = _names_keyboard()
        try:
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)
        except Exception:
            await cq.answer()
            await cq.message.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # Show a specific menu from a list button
    @app.on_callback_query(filters.regex(r"^menus:show:.+"))
    async def show_cb(_, cq: CallbackQuery):
        raw = cq.data[len(SHOW_CB_P):]
        name, text = _get_menu_ci(raw)
        log.info("menus:show: raw=%r -> key=%r found=%s", raw, name, text is not None)

        if text is None:
            return await cq.answer(f"No menu saved for {_clean(raw)}.", show_alert=True)

        try:
            await cq.message.edit_text(
                f"<b>{name} — Menu</b>\n\n{text}",
                reply_markup=_menu_keyboard(name),
                disable_web_page_preview=True,
            )
        except Exception:
            await cq.answer()
            await cq.message.reply_text(
                f"<b>{name} — Menu</b>\n\n{text}",
                reply_markup=_menu_keyboard(name),
                disable_web_page_preview=True,
            )

    # 💸 Tip placeholder (you'll wire Stripe later)
    @app.on_callback_query(filters.regex(r"^tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        await cq.answer("Tips are coming soon. Thanks for the love! 💖", show_alert=True)
