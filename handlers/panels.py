# handlers/panels.py
# Main “Menus” panel (model picker + per-model view) — uses the same
# case-insensitive lookup logic as /showmenu to avoid “no menu saved yet”
# when the casing/spaces differ.

from __future__ import annotations
import asyncio
import logging
from typing import List, Tuple, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

# Callback keys
CB_MODELS_LIST = "models:list"
CB_BACK        = "models:back"
CB_PICK_PREF   = "models:pick:"  # models:pick:<Name>


# ---------- helpers ----------

def _get_menu_ci(name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Case-insensitive fetch from the menu store.
    Returns (display_name, text) or (None, None) if not found.
    """
    if not name:
        return None, None

    # 1) exact key first
    txt = store.get_menu(name)
    if txt is not None:
        # use canonical display if we can find a name with same casing
        for n in store.list_names():
            if n and n.casefold() == name.casefold():
                return n, txt
        return name, txt  # fall back to provided

    # 2) CI search across stored names
    for n in store.list_names():
        if n and n.casefold() == name.casefold():
            txt = store.get_menu(n)
            if txt is not None:
                return n, txt

    return None, None


def _models_keyboard() -> InlineKeyboardMarkup:
    names = store.list_names()
    if not names:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ Create a menu with /createmenu", callback_data=CB_MODELS_LIST)]]
        )

    rows: List[List[InlineKeyboardButton]] = []
    # one name per row keeps long names readable
    for n in names:
        rows.append([InlineKeyboardButton(n, callback_data=f"{CB_PICK_PREF}{n}")])
    return InlineKeyboardMarkup(rows)


def _menu_keyboard(model_name: str, bot_username: Optional[str]) -> InlineKeyboardMarkup:
    """
    Keep the same 4 buttons you already use:
      📖 book | 💸 tip | ⬅️ back | 🏠 main
    Only Back is handled here (returns to model list). Main links to /start.
    Book/Tip remain present so your other handlers (if any) keep working.
    """
    # Deep-link to main (/start) if we know the bot username; otherwise a noop CB
    if bot_username:
        main_btn = InlineKeyboardButton("🏠 main", url=f"https://t.me/{bot_username}?start=main")
    else:
        main_btn = InlineKeyboardButton("🏠 main", callback_data=CB_MODELS_LIST)

    kb = [
        [
            InlineKeyboardButton("📖 book", callback_data=f"book:{model_name}"),
        ],
        [
            InlineKeyboardButton("💸 tip", callback_data=f"tip:{model_name}"),
        ],
        [
            InlineKeyboardButton("⬅️ back", callback_data=CB_BACK),
        ],
        [main_btn],
    ]
    return InlineKeyboardMarkup(kb)


async def _bot_username(app: Client) -> Optional[str]:
    try:
        me = await app.get_me()
        return me.username
    except Exception:
        return None


# ---------- register ----------

def register(app: Client):
    log.info("✅ handlers.panels registered (CI menu lookup)")

    # /menu or /menu <Name>
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        bot_user = await _bot_username(_)

        # If a name is provided, go straight to that model
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) == 2:
            raw = parts[1]
            disp, text = _get_menu_ci(raw)
            if text is None:
                await m.reply_text(
                    f"{raw} — menu\n\nno menu saved yet.\n\nuse /createmenu to set one.",
                    disable_web_page_preview=True,
                )
                return

            await m.reply_text(
                f"{disp} — menu\n\n{text}",
                reply_markup=_menu_keyboard(disp, bot_user),
                disable_web_page_preview=True,
            )
            return

        # Otherwise show the model list
        await m.reply_text(
            "💕 **Choose a model:**",
            reply_markup=_models_keyboard(),
        )

    # Back to the list (either key is accepted)
    @app.on_callback_query(filters.regex(f"^{CB_MODELS_LIST}$|^{CB_BACK}$"))
    async def back_to_models(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "💕 **Choose a model:**",
                reply_markup=_models_keyboard(),
            )
        except Exception:
            # Avoid MESSAGE_NOT_MODIFIED noise; fall back to answering
            await cq.answer()

    # Pick a specific model from the list
    @app.on_callback_query(filters.regex(rf"^{CB_PICK_PREF}.+"))
    async def pick_cb(_, cq: CallbackQuery):
        bot_user = await _bot_username(_)

        raw = cq.data[len(CB_PICK_PREF):]
        disp, text = _get_menu_ci(raw)

        if text is None:
            await cq.answer(f"No menu saved for {raw}.", show_alert=True)
            return

        content = f"**{disp} — Menu**\n\n{text}"
        kb = _menu_keyboard(disp, bot_user)

        try:
            await cq.message.edit_text(
                content,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            # If Telegram says MESSAGE_NOT_MODIFIED, just swallow it.
            await cq.answer()
