# handlers/menu.py
# Minimal menu creation that survives restarts (via MenuStore)

import os
from typing import Dict, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.menu_save_fix import MenuStore

MENUS = MenuStore()

# ---- load names/ids like RONI_NAME/RONI_ID etc.
def _load_models_from_env() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for k, v in os.environ.items():
        if not k.endswith("_NAME"):
            continue
        base = k[:-5]
        name = (v or "").strip()
        if not name:
            continue
        tid = (os.getenv(f"{base}_ID") or "").strip()
        if tid.isdigit():
            out[name] = int(tid)
    return out

NAME_TO_ID: Dict[str, int] = _load_models_from_env()
LOWER_TO_CANON = {n.lower(): n for n in NAME_TO_ID.keys()}

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

# ---------------- COMMANDS ----------------

def register(app: Client):

    @app.on_message(filters.command(["addmenu", "createmenu"]) & filters.user(list(NAME_TO_ID.values())))
    async def _create_menu(c: Client, m: Message):
        """Create a menu: /addmenu <model> <caption> (with optional photo)"""
        if len(m.command) < 2:
            await m.reply_text("Usage: /addmenu <model> <caption>")
            return

        model, caption = _split_first_word(" ".join(m.command[1:]))
        model_canon = LOWER_TO_CANON.get(model.lower())
        if not model_canon:
            await m.reply_text(f"Unknown model name: {model}")
            return

        photo_id = None
        if m.photo:
            photo_id = m.photo.file_id

        MENUS.set_menu(model_canon, caption, photo_id)
        await m.reply_text(f"✅ Menu saved for {model_canon}")

    @app.on_callback_query(filters.regex("^nav:main$"))
    async def _show_main(c: Client, cq: CallbackQuery):
        keys = []
        for n in sorted(NAME_TO_ID.keys()):
            keys.append([_btn(f"💘 {n}", f"menu:{n}")])
        keys.append([_btn("⬅️ Back to Main", "nav:root")])
        await cq.message.edit_text("💕 <b>Menus</b>\nPick a model whose menu is saved.",
                                   reply_markup=InlineKeyboardMarkup(keys))

    @app.on_callback_query(filters.regex(r"^menu:(.+)$"))
    async def _show_menu(c: Client, cq: CallbackQuery):
        model = cq.data.split(":",1)[1]
        item = MENUS.get_menu(model)
        if not item:
            await cq.answer("No menu saved for this model.", show_alert=True)
            return
        if item.photo_file_id:
            await cq.message.reply_photo(item.photo_file_id, caption=item.caption or f"{model}'s Menu")
        else:
            await cq.message.reply_text(item.caption or f"{model}'s Menu")
        await cq.answer()
