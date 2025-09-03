# handlers/menu.py
# Minimal menu creation that supports /createmenu in photo captions or text
import os
from typing import Dict, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# persistent store you already have
from handlers.menu_save_fix import MenuStore

MENUS = MenuStore()

# ---- load names & ids from ENV like RONI_NAME/RONI_ID, etc.
def _load_models_from_env() -> Dict[str, int]:
    out: Dict[str, int] = {}
    for k, v in os.environ.items():
        if not k.endswith("_NAME"):
            continue
        base = k[:-5]  # drop _NAME
        name = (v or "").strip()
        if not name:
            continue
        tid = (os.getenv(f"{base}_ID") or "").strip()
        if tid.isdigit():
            out[name] = int(tid)
    return out

NAME_TO_ID: Dict[str, int] = _load_models_from_env()
LOWER_TO_CANON = {n.lower(): n for n in NAME_TO_ID.keys()}  # case-insensitive map

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")

def _canon(name: str) -> str:
    return LOWER_TO_CANON.get((name or "").lower(), "")

def _contact_line(name: str) -> str:
    tid = NAME_TO_ID.get(name)
    return f'\n\nContact: <a href="tg://user?id={tid}">{name}</a>' if tid else ""

async def _send_menu_list(msg: Message):
    names = MENUS.list_names()
    if not names:
        return await msg.reply_text("No menus have been created yet.")
    rows = [[_btn(n, f"menu:show:{n}")] for n in names]
    await msg.reply_text("Choose a model:", reply_markup=InlineKeyboardMarkup(rows))

async def _send_menu_preview(msg: Message, name: str):
    item = MENUS.get_menu(name)
    if not item:
        return await msg.reply_text(f"Menu for <b>{name}</b> not found.")
    contact = _contact_line(name)
    if item.photo_file_id:
        await msg.reply_photo(item.photo_file_id, caption=(item.caption or item.name) + contact)
    else:
        await msg.reply_text(f"<b>{item.name}</b>\n{(item.caption or '(no text)')}{contact}")

def register(app: Client):

    # PUBLIC: browse menus
    @app.on_message(filters.command("menu", prefixes=["/", "!", "."]))
    async def _menu(c: Client, m: Message):
        await _send_menu_list(m)

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _cb_show(c: Client, cq: CallbackQuery):
        name = cq.data.split(":", 2)[2]
        await _send_menu_preview(cq.message, name)
        await cq.answer()

    # ADMIN: create/update menu
    # Accept both /createmenu and /addmenu to be safe
    @app.on_message(filters.command(["createmenu", "addmenu"], prefixes=["/", "!", "."]))
    async def _createmenu(c: Client, m: Message):
        """
        Works in three ways:
        1) Text message:    /createmenu Rin <caption...>
        2) Photo caption:   [photo with caption]  /createmenu Rin <caption...>
        3) Reply to photo:  reply to a photo with  /createmenu Rin <caption...>  (caption can be omitted to reuse photo's caption)
        """

        # pull "after command" from text or caption
        after = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after = m.text.split(maxsplit=1)[1]
        elif m.caption and any(m.caption.startswith(p+"createmenu") or m.caption.startswith(p+"addmenu") for p in ("/","!",".")):
            cap_parts = m.caption.split(maxsplit=1)
            after = cap_parts[1] if len(cap_parts) > 1 else ""

        # need at least a name somewhere (in args or in replied caption)
        name_raw, rest = _split_first_word(after)
        name = _canon(name_raw)

        if not name and m.reply_to_message and m.reply_to_message.caption:
            nr, rr = _split_first_word(m.reply_to_message.caption)
            cand = _canon(nr)
            if cand:
                name, rest = cand, (rest or rr)

        if not name:
            allowed = ", ".join(sorted(NAME_TO_ID.keys())) or "(none set in ENV)"
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {allowed}")

        # caption priority: explicit rest -> command caption remainder -> replied photo caption
        caption = rest
        if not caption:
            if m.caption and any(m.caption.startswith(p+"createmenu") or m.caption.startswith(p+"addmenu") for p in ("/","!",".")):
                parts = m.caption.split(maxsplit=2)
                caption = parts[2].strip() if len(parts) > 2 else ""
            elif m.reply_to_message and m.reply_to_message.caption:
                rc = m.reply_to_message.caption.strip()
                # strip leading name if present
                low = name.lower()
                caption = rc[len(name)+1:].strip() if rc.lower().startswith(low + " ") else rc

        # photo source: same message or replied photo
        photo_id = None
        if m.photo:
            photo_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_id = m.reply_to_message.photo[-1].file_id

        MENUS.set_menu(name=name, caption=caption, photo_file_id=photo_id)
        await m.reply_text(f"✅ Saved <b>{name}</b> menu ({'photo+text' if photo_id else 'text-only'}).")
