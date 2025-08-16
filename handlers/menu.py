# handlers/menu.py
# Standalone /menu + “💕 Menu” callback showing exactly four tabs:
# Roni, Ruby, Rin, Savy. Each tab shows that model's saved menu (photo + caption).
# Models add/update by sending a PHOTO with caption:
#   /addmenu <Roni|Ruby|Rin|Savy> <menu text>
#
# Storage: local JSON (MODEL_MENUS_PATH, default "model_menus.json")

import os
import json
from typing import Dict, Any, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)

# ============ CONFIG ============
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))
MODEL_MENUS_PATH = os.getenv("MODEL_MENUS_PATH", "model_menus.json")

ALLOWED_MENU_NAMES = {
    "roni": "Roni",
    "ruby": "Ruby",
    "rin":  "Rin",
    "savy": "Savy",
}

# ============ STORAGE (JSON) ============
def _load_all() -> Dict[str, Dict[str, Any]]:
    try:
        with open(MODEL_MENUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    tmp = MODEL_MENUS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MODEL_MENUS_PATH)

def _get_menu(slug: str) -> Optional[Dict[str, Any]]:
    allm = _load_all()
    return allm.get(slug)

def _set_menu(slug: str, title: str, text: str, photo_id: str) -> None:
    allm = _load_all()
    allm[slug] = {"title": title, "text": text, "photo": photo_id}
    _save_all(allm)

# ============ UI ============

def _tabs_kb() -> InlineKeyboardMarkup:
    # One row with the four fixed tabs
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Roni", callback_data="mmenu_show:roni"),
        InlineKeyboardButton("Ruby", callback_data="mmenu_show:ruby"),
        InlineKeyboardButton("Rin",  callback_data="mmenu_show:rin"),
        InlineKeyboardButton("Savy", callback_data="mmenu_show:savy"),
    ]])

def _deeplink_kb(username: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{username}?start=ready"
    return InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM Now", url=url)]])

# ============ PERMS ============

async def _is_admin_here(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _is_owner_or_super(uid: int) -> bool:
    return uid == OWNER_ID or uid == SUPER_ADMIN_ID

# ============ REGISTER ============

def register(app: Client):

    # /menu everywhere
    @app.on_message(filters.command("menu"))
    async def menu_cmd(client: Client, m: Message):
        # In DM: show the 4 tabs
        if m.chat and m.chat.type == "private":
            await m.reply_text("Pick a menu:", reply_markup=_tabs_kb())
            return

        # In groups/channels: provide DM deep link
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a public @username to open the menu in DM. Ask an admin to set it.")
        await m.reply_text(
            "Tap to DM and open the Menu:",
            reply_markup=_deeplink_kb(me.username)
        )

    # “💕 Menu” button (from dm_foolproof) points here
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("Pick a menu:", reply_markup=_tabs_kb())
        await cq.answer()

    # Show a specific model menu
    @app.on_callback_query(filters.regex("^mmenu_show:"))
    async def cb_mmenu_show(client: Client, cq: CallbackQuery):
        _, slug = cq.data.split(":", 1)
        slug = slug.strip().lower()
        title = ALLOWED_MENU_NAMES.get(slug, slug.capitalize())

        menu = _get_menu(slug)
        if not menu:
            # Friendly guidance if not yet set
            await cq.message.reply_text(
                f"<b>{title}</b>\n\nNo menu has been added yet.",
                reply_markup=_tabs_kb(),
                disable_web_page_preview=True
            )
            return await cq.answer("No menu set yet.")
        photo = menu.get("photo")
        text = f"<b>{menu.get('title') or title}</b>\n\n{menu.get('text','')}".strip()
        try:
            if photo:
                await client.send_photo(cq.from_user.id, photo, caption=text)
            else:
                await cq.message.reply_text(text, disable_web_page_preview=True
