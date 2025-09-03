# handlers/menu.py
# Menus: save/load from a simple JSON file; show model menus; Back button only.
import os, json
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

MENU_STORE_PATH = "data/menus.json"
os.makedirs("data", exist_ok=True)

def _load() -> Dict[str, dict]:
    if not os.path.exists(MENU_STORE_PATH):
        return {}
    try:
        return json.loads(open(MENU_STORE_PATH, "r", encoding="utf-8").read())
    except Exception:
        return {}

def _save(data: Dict[str, dict]) -> None:
    try:
        open(MENU_STORE_PATH, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass

MENUS: Dict[str, dict] = _load()  # keys are lowercased model names

def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def register(app: Client):

    # --- CREATE TEXT-ONLY: /createmenu <Model> <caption...>
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

    # --- CREATE WITH PHOTO: reply to a photo with /addmenu <Model> <caption...>
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
            return await m.reply_text("Reply to a photo OR send a photo with caption, then use /addmenu <Model> <caption>")

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

    # --- SHOW A MODEL MENU (support BOTH callback formats your buttons may use)
    @app.on_callback_query(filters.regex(r"^menu:(?:show:)?(.+)$"))
    async def _show_menu(c: Client, cq: CallbackQuery):
        model = cq.matches[0].group(1).strip()
        key = model.lower()
        item = MENUS.get(key)
        if not item:
            return await cq.answer("No menu saved for this model.", show_alert=True)

        # The ONLY change you asked for: add a Back button that closes this card.
        kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu:close")]])

        if item.get("photo_file_id"):
            await cq.message.reply_photo(item["photo_file_id"], caption=item.get("caption") or f"{model} Menu", reply_markup=kb_back)
        else:
            await cq.message.reply_text(item.get("caption") or f"{model} Menu", reply_markup=kb_back)

        await cq.answer()

    # --- BACK: just delete the card so the model list above is visible again
    @app.on_callback_query(filters.regex(r"^menu:close$"))
    async def _menu_close(c: Client, cq: CallbackQuery):
        try:
            await cq.message.delete()
        except Exception:
            pass
        await cq.answer("Back")
