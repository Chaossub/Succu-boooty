# handlers/menu.py
# Inline menu browser: /menus -> buttons of model names -> tap to view saved menu

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

# ────────────── USERNAMES (MATCH contact_admins.py) ──────────────
# These MUST be set in your env, without the @ (we strip it anyway)
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "Chaossub283").lstrip("@")
RUBY_USERNAME = (os.getenv("RUBY_USERNAME") or "RubyRansom").lstrip("@")
RIN_USERNAME  = (os.getenv("RIN_USERNAME")  or "your_rin_username_here").lstrip("@")
SAVY_USERNAME = (os.getenv("SAVY_USERNAME") or "your_savy_username_here").lstrip("@")

DEFAULT_BOOK_URL = os.getenv("DEFAULT_BOOK_URL", "").strip() or None


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
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)


# ────────────── BOOK URL LOGIC (LIKE contact_admins) ──────────────

def _book_url_for(model_display_name: str) -> str | None:
    """
    Resolve a '📖 Book' URL for a model.

    We don't mess with fancy slugs anymore.
    We just look at the model's name and decide whose DMs to open,
    using the same usernames envs as contact_admins.py.
    """
    n = (model_display_name or "").casefold()

    username = None
    if "roni" in n:
        username = RONI_USERNAME
        who = "Roni"
    elif "ruby" in n:
        username = RUBY_USERNAME
        who = "Ruby"
    elif "rin" in n:
        username = RIN_USERNAME
        who = "Rin"
    elif "savy" in n or "savvy" in n:
        username = SAVY_USERNAME
        who = "Savy"
    else:
        # fall back to a global booking URL if you ever want one
        if DEFAULT_BOOK_URL:
            log.info("Book: %r -> DEFAULT_BOOK_URL=%s", model_display_name, DEFAULT_BOOK_URL)
            return DEFAULT_BOOK_URL
        log.info("Book: %r -> no matching username / default URL", model_display_name)
        return None

    if not username:
        log.warning("Book: %s matched %s but username env is empty!", model_display_name, who)
        return None

    url = f"https://t.me/{username}"
    log.info("Book: %r -> %s (%s)", model_display_name, url, who)
    return url


def _menu_view_kb(model_display_name: str) -> InlineKeyboardMarkup:
    book_url = _book_url_for(model_display_name)
    rows: list[list[InlineKeyboardButton]] = []

    if book_url:
        rows.append([InlineKeyboardButton("📖 Book", url=book_url)])
    else:
        # Fallback to Contact Admins page if no URL configured
        rows.append([InlineKeyboardButton("📖 Book", callback_data="contact_admins:open")])

    rows.append([InlineKeyboardButton("💸 Tip (coming soon)", callback_data=f"{TIP_CB_P}{model_display_name}")])
    rows.append([
        InlineKeyboardButton("⬅️ Back", callback_data=LIST_CB),
        InlineKeyboardButton("🏠 Main", callback_data="portal:home"),
    ])
    return InlineKeyboardMarkup(rows)


# ────────────── REGISTER ──────────────

def register(app: Client):
    log.info(
        "✅ handlers.menu registered (storage=%s, RONI=%s RUBY=%s RIN=%s SAVY=%s)",
        "Mongo" if store.uses_mongo() else "JSON",
        RONI_USERNAME,
        RUBY_USERNAME,
        RIN_USERNAME,
        SAVY_USERNAME,
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
            await cq.message.reply_text(content, reply_markup=kb, disable_web_page_preview=True)

    # Tip placeholder (so the button does something now; Stripe later)
    @app.on_callback_query(filters.regex(r"^menus:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        model = cq.data[len(TIP_CB_P):]
        log.info("Tip button tapped for %r", model)
        await cq.answer(
            "Tips coming soon 💸 — this button is wired, we just need to hook up Stripe.",
            show_alert=True,
        )
