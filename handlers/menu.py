# handlers/menus.py
# Menus with ENV-driven names + Telegram IDs. DM or group. With/without photo.
import os
import traceback
from typing import Dict, List

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Persistent store (Mongo first, JSON fallback) — must exist as provided earlier.
from handlers.menu_save_fix import MenuStore

# Optional: trust ReqStore admins if present (won't crash if missing)
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

# ---- Allowed models + their Telegram user IDs (from ENV) ----
# Format: MENU_MODEL_MAP="Roni:6964994611,Ruby:123456789,Rin:987654321,Savy:555555555"
_raw_map = os.getenv("MENU_MODEL_MAP", "")
NAME_TO_ID: Dict[str, int] = {}
if _raw_map.strip():
    for pair in _raw_map.split(","):
        if ":" in pair:
            name, tid = pair.split(":", 1)
            name = name.strip()
            tid = tid.strip()
            if name and tid.isdigit():
                NAME_TO_ID[name] = int(tid)

ALLOWED_NAMES = set(NAME_TO_ID.keys())  # e.g. {"Roni","Ruby","Rin","Savy"}

MENUS = MenuStore()

def _is_editor(uid: int) -> bool:
    try:
        if uid == OWNER_ID:
            return True
        if uid in EXTRA_EDITORS:
            return True
        if _STORE and uid in _STORE.list_admins():
            return True
        return False
    except Exception:
        return False

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _first_word(s: str) -> str:
    return s.split()[0] if s and s.strip() else ""

def _caption_after_first_word(s: str) -> str:
    parts = s.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""

def _contact_line(name: str) -> str:
    tid = NAME_TO_ID.get(name)
    if not tid:
        return ""
    return f'\n\nContact: <a href="tg://user?id={tid}">{name}</a>'

async def _send_menu_list(msg: Message):
    names = MENUS.list_names()
    if not names:
        return await msg.reply_text("No menus have been created yet.")
    # filter to allowed names if you only want those shown
    names = [n for n in names if not ALLOWED_NAMES or n in ALLOWED_NAMES]
    if not names:
        return await msg.reply_text("No menus have been created yet.")
    rows = [[_btn(name, f"menu:show:{name}")] for name in names]
    await msg.reply_text("Choose a model:", reply_markup=InlineKeyboardMarkup(rows))

async def _send_menu_preview(msg: Message, name: str):
    item = MENUS.get_menu(name)
    if not item:
        return await msg.reply_text(f"Menu for <b>{name}</b> not found.")
    contact = _contact_line(name)
    if item.photo_file_id:
        await msg.reply_photo(photo=item.photo_file_id, caption=(item.caption or item.name) + contact)
    else:
        await msg.reply_text(f"<b>{item.name}</b>\n{(item.caption or '(no text)')}{contact}")

def register(app: Client):

    # ========== DEBUG ==========
    @app.on_message(filters.command("menudebug", prefixes=["/", "!", "."]))
    async def _menudebug(c: Client, m: Message):
        try:
            uid = m.from_user.id
            await m.reply_text(
                "🛠 <b>Menu Debug</b>\n"
                f"Storage: {'Mongo' if MENUS.uses_mongo() else 'JSON'}\n"
                f"OWNER_ID: {OWNER_ID}\n"
                f"IsEditor({uid}): { _is_editor(uid) }\n"
                f"Allowed names: {', '.join(sorted(ALLOWED_NAMES)) or '(none)'}\n"
                f"ENV MENU_MODEL_MAP: <code>{os.getenv('MENU_MODEL_MAP','')}</code>\n"
                f"ENV MENU_EDITORS: <code>{os.getenv('MENU_EDITORS','')}</code>"
            )
        except Exception as e:
            traceback.print_exc()
            await m.reply_text(f"menudebug error: <code>{type(e).__name__}: {e}</code>")

    # ========== PUBLIC ==========
    @app.on_message(filters.command("menu", prefixes=["/", "!", "."]))
    async def _menu(c: Client, m: Message):
        try:
            await _send_menu_list(m)
        except Exception as e:
            traceback.print_exc()
            await m.reply_text(f"/menu error: <code>{type(e).__name__}: {e}</code>")

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

    # ========== ADMIN (DM or GROUP) ==========
    admin_filter = filters.command(["addmenu", "changemenu", "updatecaption", "deletemenu", "listmenus", "menueditors"], prefixes=["/", "!", "."])

    @app.on_message(admin_filter)
    async def _admin_router(c: Client, m: Message):
        cmd = (m.command[0] if m.command else "").lower()
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to manage menus.")
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

    # -------- handlers --------
    async def _handle_addmenu(c: Client, m: Message):
        # Accept from text, caption, or reply
        after_cmd = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after_cmd = m.text.split(maxsplit=1)[1]
        elif m.caption and any(m.caption.startswith(p + "addmenu") for p in ("/", "!", ".")):
            after_cmd = m.caption.split(maxsplit=1)[1] if len(m.caption.split(maxsplit=1)) > 1 else ""

        if not after_cmd and not (m.reply_to_message or m.caption):
            return await m.reply_text(
                "Usage:\n/addmenu <Name> <caption...>\n"
                "Attach a photo, reply to a photo, or send without a photo for a text-only menu.\n"
                f"Allowed names: {', '.join(sorted(ALLOWED_NAMES)) or '(none set)'}"
            )

        name = _first_word(after_cmd)
        if not name:
            return await m.reply_text("Missing model name. Example: /addmenu Roni My caption…")
        if ALLOWED_NAMES and name not in ALLOWED_NAMES:
            return await m.reply_text(f"❌ Unknown model '{name}'. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")

        caption = _caption_after_first_word(after_cmd)

        # If only name supplied, fallback to caption in the message (minus the command) or reply caption
        if not caption:
            if m.caption and any(m.caption.startswith(p + "addmenu") for p in ("/", "!", ".")):
                # Strip the command and the name from caption
                # e.g., "/addmenu Roni <rest>"
                cap_parts = m.caption.split(maxsplit=2)
                caption = cap_parts[2].strip() if len(cap_parts) > 2 else ""
            elif m.reply_to_message and m.reply_to_message.caption:
                caption = m.reply_to_message.caption.strip()

        photo_file_id = None
        if m.photo:
            photo_file_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_file_id = m.reply_to_message.photo[-1].file_id

        MENUS.set_menu(name=name, caption=caption, photo_file_id=photo_file_id)
        kind = "photo+text" if photo_file_id else "text-only"
        await m.reply_text(f"✅ Saved <b>{name}</b> menu ({kind}).")

    async def _handle_changemenu(c: Client, m: Message):
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text(
                "Usage:\n/changemenu <Name> [new caption]\n"
                "Reply to a NEW photo to change the image (keeps caption unless you provide a new one)."
            )
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")
        new_caption = _caption_after_first_word(args[1]) or None

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
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
            return await m.reply_text(f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}")
        new_caption = _caption_after_first_word(args[1])
        if not new_caption:
            return await m.reply_text("Missing caption text.")
        ok = MENUS.update_caption(name, new_caption)
        if not ok:
            return await m.reply_text(f"Menu for <b>{name}</b> not found.")
        await m.reply_text(f"✅ Caption updated for <b>{name}</b>.")

    async def _handle_deletemenu(c: Client, m: Message):
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/deletemenu <Name>")
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
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
        await m.reply_text(
            "Menu editors\n"
            f"OWNER_ID: {OWNER_ID}\n"
            f"EXTRA MENU_EDITORS: {extras}\n"
            f"ReqStore admins: {admins}\n"
            f"Allowed names: {allowed}\n"
            f"Storage: {'Mongo' if MENUS.uses_mongo() else 'JSON'}"
        )
