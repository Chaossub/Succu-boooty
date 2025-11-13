# handlers/menu.py
#
# Inline menu browser:
#   /menus -> list of model names -> tap to view saved menu
#
# "📖 Book" button:
#   Resolves to https://t.me/<USERNAME> using the same style as contact_admins.py:
#     RONI_USERNAME, RUBY_USERNAME, RIN_USERNAME, SAVY_USERNAME
#   (Usernames may be set in env; defaults are provided and @ is stripped.)

import logging
import os
import re
from pyrogram import filters, Client
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
TIP_CB_P  = "menus:tip:"    # prefix: menus:tip:<Name>

# ────────────── USERNAME ENV (same pattern as contact_admins) ──────────────
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "Chaossub283").lstrip("@")
RUBY_USERNAME = (os.getenv("RUBY_USERNAME") or "RubyRansom").lstrip("@")
RIN_USERNAME  = (os.getenv("RIN_USERNAME")  or "peachyrinn").lstrip("@")
SAVY_USERNAME = (os.getenv("SAVY_USERNAME") or "savage_savy").lstrip("@")

# Map canonical menu names -> which username to use
# (Keys are lowercased + single-spaced versions of the display name)
MODEL_USER_MAP = {
    "roni": RONI_USERNAME,
    "ruby": RUBY_USERNAME,
    "rin": RIN_USERNAME,
    "savy": SAVY_USERNAME,
    "savy savannah savage": SAVY_USERNAME,  # long version, same Savy
}

# ────────────── HELPERS ──────────────

_WS_RE = re.compile(r"\s+", re.UNICODE)

def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _canon(name: str) -> str:
    """Lowercase, collapse whitespace, used for lookups."""
    s = _clean(name)
    s = _WS_RE.sub(" ", s)
    return s.casefold()

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
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)

def _book_url_for(model_display_name: str) -> str | None:
    """
    Resolve a '📖 Book' URL for a model using the same approach as contact_admins:
      https://t.me/<USERNAME> where USERNAME comes from *_USERNAME envs.
    """
    canon_name = _canon(model_display_name)
    username = MODEL_USER_MAP.get(canon_name)

    log.info("Book lookup: disp=%r canon=%r username=%r", model_display_name, canon_name, username)

    if username:
        return f"https://t.me/{username}"

    return None  # Will fall back to Contact Admins

def _menu_view_kb(model_display_name: str) -> InlineKeyboardMarkup:
    book_url = _book_url_for(model_display_name)
    rows: list[list[InlineKeyboardButton]] = []

    if book_url:
        rows.append([InlineKeyboardButton("📖 Book", url=book_url)])
    else:
        # Fallback to Contact Admins page if no username configured
        rows.append([InlineKeyboardButton("📖 Book", callback_data="contact_admins:open")])

    rows.append([InlineKeyboardButton("💸 Tip", callback_data=f"{TIP_CB_P}{model_display_name}")])
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB),
        InlineKeyboardButton("🏠 Main", callback_data="portal:home"),
    ])
    return InlineKeyboardMarkup(rows)

# ────────────── REGISTER ──────────────

def register(app: Client):
    log.info(
        "✅ handlers.menu registered (storage=%s)",
        "Mongo" if store.uses_mongo() else "JSON",
    )

    # List all menus as buttons
    @app.on_message(filters.command("menus"))
    async def menus_cmd(_, m: Message):
        kb = _names_keyboard()
        await m.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=kb)

    # Show a specific menu by name via command
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
            reply_markup=_menu_view_kb(name),
            disable_web_page_preview=True,
        )

    # Open / refresh the list UI (from Panels "💞 Menus" button)
    @app.on_callback_query(filters.regex(f"^{OPEN_CB}$|^{LIST_CB}$|^panels:root$"))
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

        content = f"<b>{name} — Menu</b>\n\n{text}"
        kb = _menu_view_kb(name)
        try:
            await cq.message.edit_text(content, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.answer()
            await cq.message.reply_text(
                content, reply_markup=kb, disable_web_page_preview=True
            )

    # Tip placeholder (Stripe will hook in here later)
    @app.on_callback_query(filters.regex(r"^menus:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        model = cq.data[len(TIP_CB_P):]
        await cq.answer(
            "Tips coming soon 💸 — the button is wired, just hook up the processor next.",
            show_alert=True,
        )
