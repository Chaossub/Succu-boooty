# handlers/menus.py
# Menus with ENV-driven single-word names + Telegram IDs.
# /addmenu <Name> works with photo, reply-to-photo, or text-only.
import os
import shlex
from typing import Optional, List, Dict

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Persistent store (Mongo first, JSON fallback) — must exist as provided earlier.
from handlers.menu_save_fix import MenuStore

# Optional: trust ReqStore admins if present
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
    if uid == OWNER_ID:
        return True
    if uid in EXTRA_EDITORS:
        return True
    if _STORE and uid in _STORE.list_admins():
        return True
    return False

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _first_word(s: str) -> str:
    # Single-word model names only (Roni/Ruby/Rin/Savy)
    return s.split()[0] if s.strip() else ""

def _caption_after_first_word(s: str) -> str:
    parts = s.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""

def _contact_line(name: str) -> str:
    """Clickable contact line using Telegram user ID from ENV."""
    tid = NAME_TO_ID.get(name)
    if not tid:
        return ""
    # Works even if the user has no @username
    return f'\n\nContact: <a href="tg://user?id={tid}">{name}</a>'

async def _send_menu_list(msg: Message):
    names = MENUS.list_names()
    if not names:
        return await msg.reply_text("No menus have been created yet.")
    # Only show names that are still allowed (if you want to filter)
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

    # Public menu browser
    @app.on_message(filters.private & filters.command("menu"))
    async def _menu(c: Client, m: Message):
        await _send_menu_list(m)

    @app.on_callback_query(filters.regex(r"^menu:list$"))
    async def _cb_list(c: Client, cq: CallbackQuery):
        await _send_menu_list(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _cb_show(c: Client, cq: CallbackQuery):
        name = cq.data.split(":", 2)[2]
        await _send_menu_preview(cq.message, name)
        await cq.answer()

    # ---- Admin Ops ----

    @app.on_message(filters.private & filters.command("addmenu"))
    async def _addmenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to add menus.")

        # Pull raw args from text or caption (when command is in photo caption)
        after_cmd = ""
        if m.text and len(m.text.split(maxsplit=1)) > 1:
            after_cmd = m.text.split(maxsplit=1)[1]
        elif m.caption and m.caption.startswith("/addmenu"):
            # Remove the command itself
            after_cmd = m.caption[len("/addmenu"):].strip()

        if not after_cmd and not m.reply_to_message and not m.caption:
            return await m.reply_text(
                "Usage:\n"
                "/addmenu <Name> <caption...>\n\n"
                "Attach a photo, reply to a photo, or send without a photo for a text-only menu.\n"
                f"Allowed names: {', '.join(sorted(ALLOWED_NAMES)) or '(none set)'}"
            )

        name = _first_word(after_cmd)
        if not name:
            return await m.reply_text("Missing model name. Example: /addmenu Roni My caption…")

        if ALLOWED_NAMES and name not in ALLOWED_NAMES:
            return await m.reply_text(
                f"❌ Unknown model '{name}'. Allowed: {', '.join(sorted(ALLOWED_NAMES))}"
            )

        caption = _caption_after_first_word(after_cmd)
        # Fallback: when user typed only name, use the message or reply caption
        if not caption:
            if m.caption and m.caption.startswith("/addmenu"):
                # strip command + name from caption
                cap = m.caption[len("/addmenu"):].strip()
                caption = _caption_after_first_word(cap)
            elif m.reply_to_message and m.reply_to_message.caption:
                caption = m.reply_to_message.caption.strip()

        # Photo detection: same message or reply
        photo_file_id = None
        if m.photo:
            photo_file_id = m.photo[-1].file_id
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_file_id = m.reply_to_message.photo[-1].file_id

        MENUS.set_menu(name=name, caption=caption, photo_file_id=photo_file_id)
        kind = "photo+text" if photo_file_id else "text-only"
        await m.reply_text(f"✅ Saved <b>{name}</b> menu ({kind}).")

    @app.on_message(filters.private & filters.command("changemenu"))
    async def _changemenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to change menus.")

        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text(
                "Usage:\n/changemenu <Name> [new caption]\n"
                "Reply to a NEW photo to change the image (keeps caption unless you provide a new one)."
            )
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
            return await m.reply_text(
                f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}"
            )
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

    @app.on_message(filters.private & filters.command("updatecaption"))
    async def _updatecaption(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to change menus.")
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text(
                "Usage:\n/updatecaption <Name> <new caption...>\n"
                "Example: /updatecaption Roni New text"
            )
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
            return await m.reply_text(
                f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}"
            )
        new_caption = _caption_after_first_word(args[1])
        if not new_caption:
            return await m.reply_text("Missing caption text.")
        ok = MENUS.update_caption(name, new_caption)
        if not ok:
            return await m.reply_text(f"Menu for <b>{name}</b> not found.")
        await m.reply_text(f"✅ Caption updated for <b>{name}</b>.")

    @app.on_message(filters.private & filters.command("deletemenu"))
    async def _deletemenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to delete menus.")
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/deletemenu <Name>")
        name = _first_word(args[1])
        if not name or (ALLOWED_NAMES and name not in ALLOWED_NAMES):
            return await m.reply_text(
                f"❌ Unknown or missing name. Allowed: {', '.join(sorted(ALLOWED_NAMES))}"
            )
        ok = MENUS.delete_menu(name)
        await m.reply_text("🗑️ Deleted." if ok else f"Menu for <b>{name}</b> not found.")

    @app.on_message(filters.private & filters.command("listmenus"))
    async def _listmenus(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to manage menus.")
        names = MENUS.list_names()
        if not names:
            return await m.reply_text("(none)")
        # Show allowed only, and include their TG IDs
        lines = []
        for n in sorted(names, key=str.lower):
            if ALLOWED_NAMES and n not in ALLOWED_NAMES:
                continue
            tid = NAME_TO_ID.get(n)
            lines.append(f"• {n}" + (f" — <code>{tid}</code>" if tid else ""))
        await m.reply_text("\n".join(lines) if lines else "(none)")

    @app.on_message(filters.private & filters.command("menueditors"))
    async def _menueditors(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to view this.")
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
