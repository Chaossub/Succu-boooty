# Inline menu browser:
#   /menus -> buttons of model names -> tap to view saved menu
#
# Booking links:
#   We use per-model env vars.
#
#   Exact mapping (based on the *menu name* you saved with /createmenu):
#
#     "Roni" -> BOOK_URL_RONI
#     "Ruby" -> BOOK_URL_RUBY
#     "Rin"  -> BOOK_URL_RIN
#     "Savy" -> BOOK_URL_SAVY
#
#   If a model name isn't in the map, we fall back to a generic slug:
#     name "Some Girl" -> BOOK_URL_SOME_GIRL
#
#   Env values can be:
#     - username            -> "chaossub283"
#     - @username           -> "@chaossub283"
#     - https://t.me/user   -> used as-is
#     - tg://resolve?...    -> used as-is
#
#   Optional global fallback:
#     DEFAULT_BOOK_URL      (same formats allowed)

import logging
import re
import os
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

# Hard mapping for your main models
MODEL_ENV_MAP = {
    "roni": "BOOK_URL_RONI",
    "ruby": "BOOK_URL_RUBY",
    "rin":  "BOOK_URL_RIN",
    "savy": "BOOK_URL_SAVY",
}


def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()


def _slug_env_key(name: str) -> str:
    # Generic slug if not in MODEL_ENV_MAP: BOOK_URL_<SLUG>
    s = re.sub(r"\s+", "_", name.strip())
    s = re.sub(r"[^A-Za-z0-9_]+", "", s)
    return s.upper()


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


def _normalize_book_value(raw: str | None) -> str | None:
    """
    Normalize BOOK_URL_* and DEFAULT_BOOK_URL values.

    Allowed inputs:
      - username            -> "chaossub283"
      - @username           -> "@chaossub283"
      - https://t.me/user   -> left as-is
      - tg://...            -> left as-is
    """
    if not raw:
        return None
    v = raw.strip()
    if not v:
        return None

    # Already a URL? keep as-is.
    if re.match(r"^(?:https?://|tg://)", v, flags=re.IGNORECASE):
        return v

    # Otherwise treat as username
    v = v.lstrip("@")
    if not v:
        return None
    return f"https://t.me/{v}"


def _book_url_for(model_display_name: str) -> str | None:
    """
    Resolve a '📖 Book' URL for a model.

    Priority:
      1) MODEL_ENV_MAP[name.lower()]  -> BOOK_URL_...
      2) BOOK_URL_<SLUG_OF_MODEL_NAME>
      3) DEFAULT_BOOK_URL
    """
    disp = _clean(model_display_name)
    key_ci = disp.casefold()

    # 1) Hard map (Roni, Ruby, Rin, Savy)
    env_name = MODEL_ENV_MAP.get(key_ci)
    if env_name:
        raw = os.getenv(env_name)
        url = _normalize_book_value(raw)
        log.info("Book URL for %r via %s -> %r", disp, env_name, url)
        if url:
            return url

    # 2) Slug fallback (for any other models)
    slug = _slug_env_key(disp)
    env_name = f"BOOK_URL_{slug}"
    raw = os.getenv(env_name)
    url = _normalize_book_value(raw)
    log.info("Book URL for %r via %s -> %r", disp, env_name, url)
    if url:
        return url

    # 3) Global fallback
    default = _normalize_book_value(os.getenv("DEFAULT_BOOK_URL"))
    log.info("Book URL for %r via DEFAULT_BOOK_URL -> %r", disp, default)
    return default


def _menu_view_kb(model_display_name: str) -> InlineKeyboardMarkup:
    book_url = _book_url_for(model_display_name)
    rows: list[list[InlineKeyboardButton]] = []

    if book_url:
        rows.append([InlineKeyboardButton("📖 Book", url=book_url)])
    else:
        # Fallback to Contact Admins page if no URL configured at all
        rows.append([InlineKeyboardButton("📖 Book", callback_data="contact_admins:open")])

    rows.append([InlineKeyboardButton("💸 Tip", callback_data=f"{TIP_CB_P}{model_display_name}")])
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB),
        InlineKeyboardButton("🏠 Main", callback_data="portal:home"),
    ])
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ handlers.menu registered (storage=%s)", "Mongo" if store.uses_mongo() else "JSON")

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
            await cq.message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)

    # Tip placeholder (Stripe will hook in here later)
    @app.on_callback_query(filters.regex(r"^menus:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        model = cq.data[len(TIP_CB_P):]
        await cq.answer(
            "Tips coming soon 💸 — the button is wired, just hook up the processor next.",
            show_alert=True,
        )
