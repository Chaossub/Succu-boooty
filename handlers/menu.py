# handlers/menus.py
import os
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from menu_store import MenuStore

# Optional – also trusts ReqStore admins if present
try:
    from req_store import ReqStore
    _STORE = ReqStore()
except Exception:
    _STORE = None

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
MENU_EDITORS_ENV = {
    int(x.strip()) for x in (os.getenv("MENU_EDITORS", "") or "").split(",") if x.strip().isdigit()
}

MENUS = MenuStore()

def _is_editor(uid: int) -> bool:
    if uid == OWNER_ID: return True
    if uid in MENU_EDITORS_ENV: return True
    if _STORE and uid in _STORE.list_admins(): return True
    return False

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

async def _send_menu_list(msg: Message):
    names = MENUS.list_names()
    if not names:
        return await msg.reply_text("No menus have been created yet.")
    rows = [[_btn(name, f"menu:show:{name}")] for name in names]
    await msg.reply_text(
        "Choose a model:",
        reply_markup=InlineKeyboardMarkup(rows)
    )

async def _send_menu_preview(msg: Message, name: str):
    item = MENUS.get_menu(name)
    if not item:
        return await msg.reply_text(f"Menu for <b>{name}</b> not found.")
    # Send as photo + caption (like your flyers)
    await msg.reply_photo(
        photo=item.photo_file_id,
        caption=item.caption or f"{item.name}"
    )

def register(app: Client):

    @app.on_message(filters.private & filters.command("menu"))
    async def _menu(c: Client, m: Message):
        await _send_menu_list(m)

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _menu_show(c: Client, cq: CallbackQuery):
        name = cq.data.split(":", 2)[2]
        await _send_menu_preview(cq.message, name)
        await cq.answer()

    @app.on_message(filters.private & filters.command("listmenus"))
    async def _listmenus(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to manage menus.")
        names = MENUS.list_names()
        if not names:
            return await m.reply_text("(none)")
        await m.reply_text("• " + "\n• ".join(names))

    @app.on_message(filters.private & filters.command("menueditors"))
    async def _menueditors(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to view this.")
        extra = ", ".join(str(x) for x in sorted(MENU_EDITORS_ENV)) or "(none)"
        admins = ", ".join(str(x) for x in (_STORE.list_admins() if _STORE else [])) or "(none)"
        await m.reply_text(
            f"OWNER_ID: {OWNER_ID}\nMENU_EDITORS: {extra}\nReqStore admins: {admins}"
        )

    @app.on_message(filters.private & filters.command("addmenu"))
    async def _addmenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to add menus.")
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/addmenu <Model Name> <caption...>\nAttach a photo OR reply to a photo.")
        name_and_caption = args[1]

        # Prefer attached photo; otherwise look at replied-to message
        photo = None
        if m.photo:
            photo = m.photo[-1]
            caption = name_and_caption.split(maxsplit=1)[1] if len(name_and_caption.split(maxsplit=1)) > 1 else (m.caption or "")
            name = name_and_caption.split(maxsplit=1)[0]
        elif m.reply_to_message and m.reply_to_message.photo:
            photo = m.reply_to_message.photo[-1]
            # Here the full args after command are the model name + caption
            # Require at least a name
            parts = name_and_caption.split(maxsplit=1)
            name = parts[0]
            caption = parts[1] if len(parts) > 1 else (m.reply_to_message.caption or "")
        else:
            return await m.reply_text("Please attach a photo (or reply to a photo) with the command.")

        file_id = photo.file_id
        MENUS.set_menu(name, file_id, caption or name)
        await m.reply_text(f"✅ Menu saved for <b>{name}</b>.")

    @app.on_message(filters.private & filters.command("changemenu"))
    async def _changemenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to change menus.")
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/changemenu <Model Name>\nRun this as a reply to a NEW photo.\nOptionally include a new caption after the name.")
        parts = args[1].split(maxsplit=1)
        name = parts[0]
        new_caption = parts[1] if len(parts) > 1 else None

        if not (m.reply_to_message and m.reply_to_message.photo):
            return await m.reply_text("Reply to a NEW photo with /changemenu <Model Name> [new caption].")

        file_id = m.reply_to_message.photo[-1].file_id
        ok = MENUS.update_photo(name, file_id, new_caption=new_caption)
        if not ok:
            return await m.reply_text(f"Menu for <b>{name}</b> not found. Use /addmenu first.")
        await m.reply_text(f"✅ Menu image updated for <b>{name}</b>.")

    @app.on_message(filters.private & filters.command("deletemenu"))
    async def _deletemenu(c: Client, m: Message):
        if not _is_editor(m.from_user.id):
            return await m.reply_text("🚫 You’re not allowed to delete menus.")
        args = (m.text or "").split(maxsplit=1)
        if len(args) < 2:
            return await m.reply_text("Usage:\n/deletemenu <Model Name>")
        name = args[1].strip()
        ok = MENUS.delete_menu(name)
        await m.reply_text("🗑️ Deleted." if ok else f"Menu for <b>{name}</b> not found.")

    # Quick button-based navigation from your main panel (if you wire callbacks):
    @app.on_callback_query(filters.regex(r"^menu:list$"))
    async def _cb_list(c: Client, cq: CallbackQuery):
        await _send_menu_list(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:show:(.+)$"))
    async def _cb_show(c: Client, cq: CallbackQuery):
        name = cq.data.split(":", 2)[2]
        await _send_menu_preview(cq.message, name)
        await cq.answer()
