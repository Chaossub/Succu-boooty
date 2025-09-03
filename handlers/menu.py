# handlers/menu.py
# Persist menus in data/menus.json (single, consistent path).
# /createmenu <Model> <text> saves a text menu.
# Tapping a model shows it; Back returns to the model list.
# Safe across multiple workers (reloads before showing), atomic saves.

import os, json, tempfile
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

DATA_DIR = "data"
STORE_PATH = os.path.join(DATA_DIR, "menus.json")
os.makedirs(DATA_DIR, exist_ok=True)

def _load() -> dict:
    # Prefer data/menus.json. If missing, fall back once to ./menus.json (legacy).
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    legacy = "menus.json"
    if os.path.exists(legacy):
        try:
            with open(legacy, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _atomic_save(data: dict) -> None:
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

# process-local cache (writes update this; reads will refresh)
MENUS = _load()

def _model_and_text(after: str) -> tuple[str, str]:
    s = (after or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def register(app: Client):

    # ---- CREATE: /createmenu <Model> <caption...>
    # (Text-only menus. If you need photo menus later, we can add it cleanly.)
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

        model, caption = _model_and_text(after)
        if not model or not caption:
            return await m.reply_text("Usage: /createmenu <Model> <caption>")

        key = model.lower()
        MENUS[key] = {"caption": caption}  # text-only (simple & robust)
        _atomic_save(MENUS)
        await m.reply_text(f"✅ Saved <b>{model}</b> menu.")

    # ---- MENU LIST (callback: 'menu')
    @app.on_callback_query(filters.regex(r"^menu$"))
    async def _menu_list(c: Client, cq: CallbackQuery):
        kb = [
            [InlineKeyboardButton("💘 Roni", callback_data="show:roni"),
             InlineKeyboardButton("💘 Ruby", callback_data="show:ruby")],
            [InlineKeyboardButton("💘 Rin",  callback_data="show:rin"),
             InlineKeyboardButton("💘 Savy", callback_data="show:savy")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")]
        ]
        await cq.message.edit_text(
            "💕 <b>Menus</b>\nPick a model whose menu is saved.",
            reply_markup=InlineKeyboardMarkup(kb),
            disable_web_page_preview=True
        )
        await cq.answer()

    # ---- SHOW A MODEL (callback: 'show:<name>')
    @app.on_callback_query(filters.regex(r"^show:(?P<name>.+)$"))
    async def _show_model(c: Client, cq: CallbackQuery):
        name = cq.matches[0].group("name").strip()
        key = name.lower()

        # RELOAD before read so new menus are visible across workers/restarts
        latest = _load()
        item = latest.get(key) or MENUS.get(key)
        if not item:
            return await cq.answer("❌ No menu saved for this model.", show_alert=True)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu")]])
        text = item.get("caption") or f"{name.title()} Menu"
        await cq.message.edit_text(text, reply_markup=kb)
        await cq.answer()

    # ---- Back to main panel (panels.main_menu)
    @app.on_callback_query(filters.regex(r"^back_main$"))
    async def _back_main(c: Client, cq: CallbackQuery):
        from handlers.panels import main_menu
        await main_menu(cq.message)
        await cq.answer()
