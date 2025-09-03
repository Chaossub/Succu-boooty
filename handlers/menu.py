# handlers/menu.py
# Keep it minimal: create menus reliably + proper Back behavior.
# Uses your existing handlers/menu_save_fix.py for persistence.

import os
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from handlers.menu_save_fix import MenuStore

MENUS = MenuStore()

# ---- load names/ids like RONI_NAME/RONI_ID etc. (case-insensitive match)
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
MODEL_IDS = set(NAME_TO_ID.values())

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
EXTRA_EDITORS = {
    int(x.strip()) for x in (os.getenv("MENU_EDITORS", "") or "").split(",") if x.strip().isdigit()
}

def _is_editor(uid: int) -> bool:
    # Owner, extra editors, or any of the model IDs can create/update menus
    return uid == OWNER_ID or uid in EXTRA_EDITORS or uid in MODEL_IDS

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")

def _canon(name: str) -> str:
    return LOWER_TO_CANON.get((name or "").lower(), "")

def _contact_line(name: str) -> str:
    tid = NAME_TO_ID.get(name)
    return f'\n\nContact: <a href="tg://user?id={tid}">{name}</a>' if tid else ""

async def _send_menu_list(msg: Message):
    names = MENUS.list_names()
    if not names:
        await msg.reply_text("No menus have been created yet.")
        return
    # order buttons in two columns
    rows = []
    row = []
    for n in sorted(names, key=str.lower):
        row.append(_btn(f"💘 {n}", f"menu:show:{n}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("⬅️ Back to Main", "nav:root")])
    await msg.reply_text(
        "💕 <b>Menus</b>\nPick a model whose menu is saved.",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def _send_menu_preview(msg: Message, name: str):
    item = MENUS.get_menu(name)
    if not item:
        await msg.reply_text(f"Menu for <b>{name}</b> not found.")
        return
    contact = _contact_line(name)
    kb = InlineKeyboardMarkup([[ _btn("⬅️ Back", "menu:close") ]])
    if item.photo_file_id:
        await msg.reply_photo(
            item.photo_file_id,
            caption=(item.caption or f"{name}'s Menu") + contact,
            reply_markup=kb
        )
    else:
        await msg.reply_text(
            f"<b>{name}</b>\n{(item.caption or '(no text)')}{contact}",
            reply_markup=kb
        )

def register(app: Client):

    # ---------- PUBLIC: browse ----------
    @app.on_message(filters.command("menu", prefixes=["/", "!", "."]))
    async def _menu(c: Client, m: Message):
        await _send_menu_list(m)

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _cb_show(c: Client, cq: CallbackQuery):
        name = cq.data.split(":", 2)[2]
        await _send_menu_preview(cq.message, name)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:close$"))
    async def _cb_close(c: Client, cq: CallbackQuery):
        # Delete the menu card so the list above is visible again
        try:
            await cq.message.delete()
        except Exception:
            pass
        await cq.answer("Back")

    # ---------- ADMIN: create/update ----------
    @app.on_message(filters.command(["createmenu", "addmenu"], prefixes=["/", "!", "."]))
    async def _createmenu(c: Client, m: Message):
        # Permissions
        if not _is_editor(m.from_user.id):
            return

        # Parse args from text OR caption
        after = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after = m.text.split(maxsplit=1)[1]
        elif m.caption:
            cap = m.caption.strip()
            for p in ("/", "!", "."):
                if cap.startswith(p + "createmenu") or cap.startswith(p + "addmenu"):
                    parts = cap.split(maxsplit=1)
                    after = parts[1] if len(parts) > 1 else ""
                    break

        # Extract <Name> <caption...>
        name_raw, rest = _split_first_word(after)
        name = _canon(name_raw)

        # If name missing, try first word of replied photo caption
        if not name and m.reply_to_message and m.reply_to_message.caption:
            nr, rr = _split_first_word(m.reply_to_message.caption)
            cand = _canon(nr)
            if cand:
                name, rest = cand, (rest or rr)

        if not name:
            allowed = ", ".join(sorted(NAME_TO_ID.keys())) or "(none set in .env)"
            await m.reply_text(f"❌ Unknown or missing name. Allowed: {allowed}")
            return

        # Caption priority: explicit rest > command caption tail > replied-photo caption
        caption = rest
        if not caption and m.caption:
            cap = m.caption.strip()
            for p in ("/", "!", "."):
                if cap.startswith(p + "createmenu") or cap.startswith(p + "addmenu"):
                    parts = cap.split(maxsplit=2)
                    caption = parts[2].strip() if len(parts) > 2 else ""
                    break
        if not caption and m.reply_to_message and m.reply_to_message.caption:
            rc = m.reply_to_message.caption.strip()
            low = name.lower()
            caption = rc[len(name)+1:].strip() if rc.lower().startswith(low + " ") else rc

        # Photo from this message or replied photo
        photo_id = None
        if m.photo:
            photo_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_id = m.reply_to_message.photo[-1].file_id

        MENUS.set_menu(name=name, caption=caption, photo_file_id=photo_id)
        await m.reply_text(
            f"✅ Saved <b>{name}</b> menu ({'photo+text' if photo_id else 'text-only'})."
        )
