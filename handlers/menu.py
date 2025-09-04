# handlers/menu.py
# Menus: save to data/menus.json (single path), atomic writes, reload-before-show.
# Commands:
#   /createmenu <Model> <caption...>
# Callbacks:
#   menu            -> list models
#   show:<name>     -> show that model's menu
#   back_main       -> call panels.main_menu()

import os, json, tempfile
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

DATA_DIR = "data"
STORE_PATH = os.path.join(DATA_DIR, "menus.json")
os.makedirs(DATA_DIR, exist_ok=True)

def _load() -> Dict[str, dict]:
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _atomic_save(data: Dict[str, dict]) -> None:
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix="menus.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STORE_PATH)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

MENUS: Dict[str, dict] = _load()  # in-RAM cache, updated on write

def _first_rest(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def register(app: Client):

    # ---- create text-only: /createmenu <Model> <caption...>
    @app.on_message(filters.command("createmenu", prefixes=["/", "!", "."]))
    async def _create_menu(c: Client, m: Message):
        rest = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            rest = m.text.split(maxsplit=1)[1]
        elif m.caption:
            cap = m.caption.strip()
            for p in ("/", "!", "."):
                if cap.startswith(p + "createmenu"):
                    parts = cap.split(maxsplit=1)
                    rest = parts[1] if len(parts) > 1 else ""
                    break

        model, caption = _first_rest(rest)
        if not model or not caption:
            return await m.reply_text("Usage: /createmenu <Model> <caption>")

        key = model.lower()
        MENUS[key] = {"caption": caption}
        _atomic_save(MENUS)
        await m.reply_text(f"✅ Saved <b>{model}</b> menu.")

    # ---- list models (callback: 'menu')
    @app.on_callback_query(filters.regex(r"^menu$"))
    async def _menu_list(c: Client, cq: CallbackQuery):
        rows = [
            [InlineKeyboardButton("💘 Roni", callback_data="show:roni"),
             InlineKeyboardButton("💘 Ruby", callback_data="show:ruby")],
            [InlineKeyboardButton("💘 Rin",  callback_data="show:rin"),
             InlineKeyboardButton("💘 Savy", callback_data="show:savy")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")],
        ]
        await cq.message.edit_text("💕 <b>Menus</b>\nPick a model whose menu is saved.",
                                   reply_markup=InlineKeyboardMarkup(rows),
                                   disable_web_page_preview=True)
        await cq.answer()

    # ---- show a model (callbacks: 'show:<name>')
    @app.on_callback_query(filters.regex(r"^show:(?P<name>.+)$"))
    async def _show_model(c: Client, cq: CallbackQuery):
        name = cq.matches[0].group("name").strip()
        key = name.lower()

        # reload from disk so changes are visible across workers/restarts
        latest = _load()
        item = latest.get(key) or MENUS.get(key)
        if not item:
            return await cq.answer("❌ No menu saved for this model.", show_alert=True)

        text = item.get("caption") or f"{name.title()} Menu"
        rows = [[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]
        await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup(rows))
        await cq.answer()

    # ---- back to main panel (handled by panels.main_menu)
    @app.on_callback_query(filters.regex(r"^back_main$"))
    async def _back_main(c: Client, cq: CallbackQuery):
        from handlers.panels import main_menu
        await main_menu(cq.message)
        await cq.answer()
