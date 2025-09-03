# handlers/menu.py
# Menus: create (text/photo), persist to data/menus.json, show with Back.
# Supports callback formats: "menu:<Name>" and "menu:show:<Name>".
# Back button uses "menu:close" and deletes only the opened card.

import os
import json
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ---------- simple JSON store ----------
DATA_DIR = "data"
MENU_STORE_PATH = os.path.join(DATA_DIR, "menus.json")
os.makedirs(DATA_DIR, exist_ok=True)

def _load() -> Dict[str, dict]:
    if not os.path.exists(MENU_STORE_PATH):
        return {}
    try:
        with open(MENU_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data: Dict[str, dict]) -> None:
    try:
        with open(MENU_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# in-memory cache (updated on writes; reads will re-load when showing)
MENUS: Dict[str, dict] = _load()  # keys: lowercased model names


# ---------- helpers ----------
def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


# ---------- register handlers ----------
def register(app: Client):

    # ---- CREATE TEXT-ONLY ----
    # /createmenu <Model> <caption...>
    @app.on_message(filters.command("createmenu", prefixes=["/", "!", "."]))
    async def _create_menu(c: Client, m: Message):
        after = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after = m.text.split(maxsplit=1)[1]
        elif m.caption:
            cap = m.caption.strip()
            for p in ("/", "!", "."):
                if cap.startswith(p + "createmenu"):
                    parts = cap.split(maxsplit=1)
                    after = parts[1] if len(parts) > 1 else ""
                    break

        model_raw, caption = _split_first_word(after)
        if not model_raw or not caption:
            return await m.reply_text("Usage: /createmenu <Model> <caption>")

        key = model_raw.lower()
        MENUS[key] = {"caption": caption, "photo_file_id": None}
        _save(MENUS)
        await m.reply_text(f"✅ Saved <b>{model_raw}</b> menu (text-only).")

    # ---- CREATE WITH PHOTO ----
    # Reply to a photo (or send a photo with the command in caption):
    # /addmenu <Model> <caption...>
    @app.on_message(filters.command("addmenu", prefixes=["/", "!", "."]))
    async def _add_menu(c: Client, m: Message):
        after = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after = m.text.split(maxsplit=1)[1]
        elif m.caption:
            cap = m.caption.strip()
            for p in ("/", "!", "."):
                if cap.startswith(p + "addmenu"):
                    parts = cap.split(maxsplit=1)
                    after = parts[1] if len(parts) > 1 else ""
                    break

        model_raw, caption = _split_first_word(after)
        if not model_raw or not caption:
            return await m.reply_text(
                "Reply to a photo OR send a photo with caption, then use /addmenu <Model> <caption>"
            )

        # photo can be on this message or the replied message
        photo_id = None
        if m.photo:
            photo_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_id = m.reply_to_message.photo[-1].file_id
        if not photo_id:
            return await m.reply_text("Please attach a photo or reply to a photo with the command.")

        key = model_raw.lower()
        MENUS[key] = {"caption": caption, "photo_file_id": photo_id}
        _save(MENUS)
        await m.reply_text(f"✅ Saved <b>{model_raw}</b> menu (photo+text).")

    # ---- SHOW A MODEL MENU (supports both callback formats; excludes 'menu:close') ----
    @app.on_callback_query(filters.regex(r"^menu:(?:show:)?(?P<name>(?!close$).+)$"))
    async def _show_menu(c: Client, cq: CallbackQuery):
        # Safety: if some broad handler matched, let the close handler take it.
        if cq.data == "menu:close":
            return

        name = cq.matches[0].group("name").strip()
        key = name.lower()

        # Reload from disk so new/updated menus are always visible across processes.
        try:
            latest = _load()
        except Exception:
            latest = MENUS
        item = latest.get(key) or MENUS.get(key)

        if not item:
            return await cq.answer("No menu saved for this model.", show_alert=True)

        # Back button — delete just this menu card so the list remains visible.
        kb_back = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="menu:close")]]
        )

        if item.get("photo_file_id"):
            await cq.message.reply_photo(
                item["photo_file_id"],
                caption=item.get("caption") or f"{name} Menu",
                reply_markup=kb_back,
            )
        else:
            await cq.message.reply_text(
                item.get("caption") or f"{name} Menu",
                reply_markup=kb_back,
            )

        await cq.answer()

    # ---- BACK: delete the opened menu card ----
    @app.on_callback_query(filters.regex(r"^menu:close$"))
    async def _menu_close(c: Client, cq: CallbackQuery):
        try:
            await cq.message.delete()
        except Exception:
            pass
        await cq.answer("Back")
