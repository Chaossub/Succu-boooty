# handlers/menu.py
# Minimal, loud, and robust menus module:
# - guarantees register(app)
# - DM + group compatible
# - /pingmenu and /menudebug to prove it's wired
# - /addmenu works with or without photo
# - /menu shows saved menus

import os
import traceback
from typing import Dict, List, Tuple

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Persistent store (Mongo first, JSON fallback).
# Make sure you have handlers/menu_save_fix.py from earlier messages.
from handlers.menu_save_fix import MenuStore

# Optional: accept ReqStore admins too
try:
    from req_store import ReqStore
    _STORE = ReqStore()
except Exception:
    _STORE = None

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
EXTRA_EDITORS = {
    int(x.strip())
    for x in (os.getenv("MENU_EDITORS", "") or "").split(",")
    if x.strip().isdigit()
}

def _load_models_from_env() -> Dict[str, int]:
    """
    Merge models from two styles:
      1) MENU_MODEL_MAP="Roni:696...,Ruby:...,Rin:...,Savy:..."
      2) any number of *_NAME + *_ID pairs (e.g., RONI_NAME/RONI_ID)
    Return {CanonicalName: telegram_id}
    """
    out: Dict[str, int] = {}

    # Style 1
    raw_map = os.getenv("MENU_MODEL_MAP", "")
    if raw_map.strip():
        for pair in raw_map.split(","):
            if ":" in pair:
                n, tid = pair.split(":", 1)
                n, tid = n.strip(), tid.strip()
                if n and tid.isdigit():
                    out[n] = int(tid)

    # Style 2
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
ALLOWED_NAMES = set(NAME_TO_ID.keys())
LOWER_TO_CANON = {n.lower(): n for n in ALLOWED_NAMES}

MENUS = MenuStore()

def _is_editor(uid: int) -> bool:
    try:
        if uid == OWNER_ID: return True
        if uid in EXTRA_EDITORS: return True
        if _STORE and uid in _STORE.list_admins(): return True
        return False
    except Exception:
        return False

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _split_first_word(s: str) -> Tuple[str, str]:
    s = (s or "").strip()
    if not s:
        return "", ""
    parts = s.split(maxsplit=1)
    first = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    return first, rest

def _canon_name(name: str) -> str:
    return LOWER_TO_CANON.get((name or "").lower(), "")

def _contact_line(name: str) -> str:
    tid = NAME_TO_ID.get(name)
    if not tid:
        return ""
    return f'\n\nContact: <a href="tg://user?id={tid}">{name}</a>'

async def _send_menu_list(msg: Message):
    try:
        names = MENUS.list_names()
        if not names:
            return await msg.reply_text("No menus have been created yet.")
        # Filter to allowed names (so typos don't show)
        if ALLOWED_NAMES:
            names = [n for n in names if n in ALLOWED_NAMES]
            if not names:
                return await msg.reply_text("No menus have been created yet.")
        rows = [[_btn(n, f"menu:show:{n}")] for n in names]
        await msg.reply_text("Choose a model:", reply_markup=InlineKeyboardMarkup(rows))
    except Exception as e:
        traceback.print_exc()
        await msg.reply_text(f"_send_menu_list error: <code>{type(e).__name__}: {e}</code>")

async def _send_menu_preview(msg: Message, name: str):
    try:
        item = MENUS.get_menu(name)
        if not item:
            return await msg.reply_text(f"Menu for <b>{name}</b> not found.")
        contact = _contact_line(name)
        if item.photo_file_id:
            await msg.reply_photo(item.photo_file_id, caption=(item.caption or item.name) + contact)
        else:
            await msg.reply_text(f"<b>{item.name}</b>\n{(item.caption or '(no text)')}{contact}")
    except Exception as e:
        traceback.print_exc()
        await msg.reply_text(f"_send_menu_preview error: <code>{type(e).__name__}: {e}</code>")

def register(app: Client):
    # ======= PROVE IT'S WIRED =======
    @app.on_message(filters.command("pingmenu", prefixes=["/", "!", "."]))
    async def _pingmenu(c: Client, m: Message):
        await m.reply_text("pong ✅ (handlers/menu.py is wired)")

    @app.on_message(filters.command("menudebug", prefixes=["/", "!", "."]))
    async def _menudebug(c: Client, m: Message):
        try:
            uid = m.from_user.id
            pairs = ", ".join([f"{n}:{NAME_TO_ID[n]}" for n in sorted(ALLOWED_NAMES)]) or "(none)"
            await m.reply_text(
                "🛠 <b>Menu Debug</b>\n"
                f"Storage: {'Mongo' if MENUS.uses_mongo() else 'JSON'}\n"
                f"IsEditor({uid}): {_is_editor(uid)}\n"
                f"Allowed names: {', '.join(sorted(ALLOWED_NAMES)) or '(none)'}\n"
                f"Map: <code>{pairs}</code>\n"
                f"OWNER_ID: {OWNER_ID}\n"
                f"MENU_EDITORS: <code>{os.getenv('MENU_EDITORS','')}</code>\n"
                f"MENU_MODEL_MAP: <code>{os.getenv('MENU_MODEL_MAP','')}</code>"
            )
        except Exception as e:
            traceback.print_exc()
            await m.reply_text(f"menudebug error: <code>{type(e).__name__}: {e}</code>")

    # ======= PUBLIC =======
    @app.on_message(filters.command("menu", prefixes=["/", "!", "."]))
    async def _menu(c: Client, m: Message):
        await _send_menu_list(m)

    @app.on_callback_query(filters.regex(r"^menu:list$"))
    async def _cb_list(c: Client, cq: CallbackQuery):
        try:
            await _send_menu_list(cq.message)
            await cq.answer()
        except Exception:
            traceback.print_exc()
            try: await cq.answer("Error", show_alert=True)
            except Exception: pass

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _cb_show(c: Client, cq: CallbackQuery):
        try:
            name = cq.data.split(":", 2)[2]
            await _send_menu_preview(cq.message, name)
            await cq.answer()
        except Exception:
            traceback.print_exc()
            try: await cq.answer("Error", show_alert=True)
            except Exception: pass

    # ======= ADMIN ROUTER (DM OR GROUP) =======
    admin_cmds = ["addmenu", "changemenu", "updatecaption", "deletemenu", "listmenus", "menueditors"]
    @app.on_message(filters.command(admin_cmds, prefixes=["/", "!", "."]))
    async def _admin_router(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to manage menus.")
        cmd = (m.command[0] if m.command else "").lower()
        try:
            if cmd == "addmenu":
                await _handle_addmenu(c, m)
            elif cmd == "changemenu":
                await _handle_changemenu(c, m)
            elif cmd == "updatecaption":
                await _handle_updatecaption(c, m)
            elif cmd == "deletemenu":
                await _handle_deletemenu(c, m)
            elif cmd == "listmenus":
                await _handle_listmenus(c, m)
            elif cmd == "menueditors":
                await _handle_menueditors(c, m)
        except Exception as e:
            traceback.print_exc()
            await m.reply_text(f"{cmd} error: <code>{type(e).__name__}: {e}</code>")

    # ======= INDIVIDUAL HANDLERS =======
    async def _handle_addmenu(c: Client, m: Message):
        # Collect text after command from message text or photo caption.
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after = m.text.split(maxsplit=1)[1]
        elif m.caption and any(m.caption.startswith(p+"addmenu") for p in ("/","!",".")):
            after = m.caption.split(maxsplit=1)[1] if len(m.caption.split(maxsplit=1)) > 1 else ""
        else:
            after = ""

        if not after and not (m.reply_to_message or m.caption):
            return await m.reply_text(
                "Usage:\n/addmenu <Name> <caption...>\n"
                "Attach a photo, reply to a photo, or send without a photo for a text-only menu.\n"
                f"Allowed names: {', '.join(sorted(ALLOWED_NAMES)) or '(none)'}"
            )

        # Parse name + caption
        name_raw, rest = _split_first_word(after)
        name = _canon_name(name_raw)
        if not name:
            # Try reply caption's first word
            rc = m.reply_to_message.caption.strip() if (m.reply_to_message and m.reply_to_message.caption) else ""
            nr, rr = _split_first_word(rc)
            name = _canon_name(nr)
            rest = rr if name and not rest else rest

        if not name:
            return await m.reply_text(
                f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES)) or '(none)'}"
            )

        caption = rest
        if not caption:
            if m.caption and any(m.caption.startswith(p+"addmenu") for p in ("/","!",".")):
                cap_parts = m.caption.split(maxsplit=2)
                caption = cap_parts[2].strip() if len(cap_parts) > 2 else ""
            elif m.reply_to_message and m.reply_to_message.caption:
                rc = m.reply_to_message.caption.strip()
                if rc.lower().startswith(name.lower() + " "):
                    caption = rc[len(name)+1:].strip()
                else:
                    caption = rc

        # Photo detection
        photo_file_id = None
        if m.photo:
            photo_file_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_file_id = m.reply_to_message.photo[-1].file_id

        MENUS.set_menu(name=name, caption=caption, photo_file_id=photo_file_id)
        await m.reply_text(f"✅ Saved <b>{name}</b> menu ({'photo+text' if photo_file_id else 'text-only'}).")

    async def _handle_changemenu(c: Client, m: Message):
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text(
                "Usage:\n/changemenu <Name> [new caption]\n"
                "Reply to a NEW photo to change the image (keeps caption unless you provide a new one)."
            )
        name_raw, rest = _split_first_word(args[1])
        name = _canon_name(name_raw)
        if not name:
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")
        new_caption = rest or None

        photo_file_id = None
        if m.reply_to_message and m.reply_to_message.photo:
            photo_file_id = m.reply_to_message.photo[-1].file_id
        if photo_file_id is None and new_caption is None:
            return await m.reply_text("Reply to a photo to change image or include a new caption to update text.")

        ok = MENUS.update_photo(name, photo_file_id, new_caption=new_caption)
        if not ok:
            return await m.reply_text(f"Menu for <b>{name}</b> not found. Use /addmenu first.")
        await m.reply_text(f"✅ Updated <b>{name}</b> menu.")

    async def _handle_updatecaption(c: Client, m: Message):
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/updatecaption <Name> <new caption...>")
        name_raw, rest = _split_first_word(args[1])
        name = _canon_name(name_raw)
        if not name:
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")
        if not rest:
            return await m.reply_text("Missing caption text.")
        ok = MENUS.update_caption(name, rest)
        if not ok:
            return await m.reply_text(f"Menu for <b>{name}</b> not found.")
        await m.reply_text(f"✅ Caption updated for <b>{name}</b>.")

    async def _handle_deletemenu(c: Client, m: Message):
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/deletemenu <Name>")
        name = _canon_name(args[1].split()[0])
        if not name:
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")
        ok = MENUS.delete_menu(name)
        await m.reply_text("🗑️ Deleted." if ok else f"Menu for <b>{name}</b> not found.")

    async def _handle_listmenus(c: Client, m: Message):
        names = MENUS.list_names()
        if not names:
            return await m.reply_text("(none)")
        lines = []
        for n in sorted(names, key=str.lower):
            if ALLOWED_NAMES and n not in ALLOWED_NAMES:
                continue
            tid = NAME_TO_ID.get(n)
            lines.append(f"• {n}" + (f" — <code>{tid}</code>" if tid else ""))
        await m.reply_text("\n".join(lines) if lines else "(none)")

    async def _handle_menueditors(c: Client, m: Message):
        extras = ", ".join(str(x) for x in sorted(EXTRA_EDITORS)) or "(none)"
        admins = ", ".join(str(x) for x in (_STORE.list_admins() if _STORE else [])) or "(none)"
        allowed = ", ".join(sorted(ALLOWED_NAMES)) or "(none)"
        pairs = ", ".join([f"{n}:{NAME_TO_ID[n]}" for n in sorted(ALLOWED_NAMES)]) or "(none)"
        await m.reply_text(
            "Menu editors\n"
            f"OWNER_ID: {OWNER_ID}\n"
            f"EXTRA MENU_EDITORS: {extras}\n"
            f"ReqStore admins: {admins}\n"
            f"Allowed names: {allowed}\n"
            f"Map: <code>{pairs}</code>\n"
            f"Storage: {'Mongo' if MENUS.uses_mongo() else 'JSON'}"
        )
