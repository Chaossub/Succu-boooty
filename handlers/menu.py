# /menu view with four tabs: Roni, Ruby, Rin, Savy
# Buttons: 💌 Contact (menu-only direct), ‼️ Rules, ✨ Buyer Requirements, ❔ Help, ⬅️ Back
# Add/update a photo menu via:
#   send a PHOTO with caption:  /addmenu Roni  <menu text>
#   or reply to a PHOTO with:   /addmenu Roni  <menu text>

import os, json
from typing import Dict, Any, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType

OWNER_ID       = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))
MODEL_MENUS_PATH = os.getenv("MODEL_MENUS_PATH", "model_menus.json")

ALLOWED_MENU_NAMES = {
    "roni": "Roni",
    "ruby": "Ruby",
    "rin":  "Rin",
    "savy": "Savy",
}

# ---------- storage ----------
def _load_all() -> Dict[str, Dict[str, Any]]:
    try:
        with open(MODEL_MENUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict): return data
    except Exception:
        pass
    return {}

def _save_all(data: Dict[str, Dict[str, Any]]) -> None:
    tmp = MODEL_MENUS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MODEL_MENUS_PATH)

def _get_menu(slug: str) -> Optional[Dict[str, Any]]:
    return _load_all().get(slug)

def _set_menu(slug: str, title: str, text: str, photo_id: str) -> None:
    allm = _load_all()
    allm[slug] = {"title": title, "text": text, "photo": photo_id}
    _save_all(allm)

# ---------- UI ----------
def _tabs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Roni", callback_data="mmenu_show:roni"),
            InlineKeyboardButton("Ruby", callback_data="mmenu_show:ruby"),
            InlineKeyboardButton("Rin",  callback_data="mmenu_show:rin"),
            InlineKeyboardButton("Savy", callback_data="mmenu_show:savy"),
        ],
        [InlineKeyboardButton("💌 Contact", callback_data="dmf_open_direct_menu")],
        [
            InlineKeyboardButton("‼️ Rules", callback_data="dmf_rules"),
            InlineKeyboardButton("✨ Buyer Requirements", callback_data="dmf_buyer"),
        ],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_show_help")],
        [InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")],
    ])

def _deeplink_kb(username: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{username}?start=ready"
    return InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM Now", url=url)]])

# ---------- perms ----------
async def _is_admin_here(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _is_owner_or_super(uid: int) -> bool:
    return uid in (OWNER_ID, SUPER_ADMIN_ID)

# ---------- register ----------
def register(app: Client):

    @app.on_message(filters.command("menu"))
    async def menu_cmd(client: Client, m: Message):
        if m.chat and m.chat.type == ChatType.PRIVATE:
            await m.reply_text("Pick a menu:", reply_markup=_tabs_kb())
            return
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a public @username to open the menu in DM.")
        await m.reply_text("Tap to DM and open the Menu:", reply_markup=_deeplink_kb(me.username))

    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("Pick a menu:", reply_markup=_tabs_kb()); await cq.answer()

    @app.on_callback_query(filters.regex("^mmenu_show:"))
    async def cb_mmenu_show(client: Client, cq: CallbackQuery):
        _, slug = cq.data.split(":", 1)
        slug = slug.strip().lower()
        title = ALLOWED_MENU_NAMES.get(slug, slug.capitalize())
        menu = _get_menu(slug)
        if not menu:
            await cq.message.reply_text(f"<b>{title}</b>\n\nNo menu has been added yet.",
                                        reply_markup=_tabs_kb(), disable_web_page_preview=True)
            return await cq.answer("No menu set yet.")
        photo = menu.get("photo")
        text  = f"<b>{menu.get('title') or title}</b>\n\n{menu.get('text','')}".strip()
        try:
            if photo:
                await client.send_photo(cq.from_user.id, photo, caption=text, reply_markup=_tabs_kb())
            else:
                await cq.message.reply_text(text, reply_markup=_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=_tabs_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_message(filters.command("addmenu"))
    async def addmenu_cmd(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if m.chat.type == ChatType.PRIVATE:
            if not _is_owner_or_super(uid):
                return await m.reply_text("Only the owner can set menus in DM.")
        else:
            if not await _is_admin_here(client, m.chat.id, uid):
                return await m.reply_text("Admins only.")

        photo_msg: Optional[Message] = None
        cmd_text: Optional[str] = None
        if m.photo:
            photo_msg = m; cmd_text = (m.caption or "").strip()
        elif m.reply_to_message and m.reply_to_message.photo:
            photo_msg = m.reply_to_message; cmd_text = (m.text or "").strip()
        else:
            return await m.reply_text(
                "Send a photo with caption:\n<code>/addmenu Roni Your menu text…</code>\n\n"
                "Or reply to a photo with:\n<code>/addmenu Roni Your menu text…</code>"
            )

        if not cmd_text:
            return await m.reply_text("Caption is empty. Usage:\n<code>/addmenu Roni Your menu text…</code>")

        parts = cmd_text.split(maxsplit=2)
        if len(parts) < 3:
            return await m.reply_text("Usage:\n<code>/addmenu Roni Your menu text…</code>")

        _, raw_name, menu_text = parts
        slug = raw_name.strip().lower()
        if slug not in ALLOWED_MENU_NAMES:
            return await m.reply_text("Invalid name. Choose one of: Roni, Ruby, Rin, Savy")

        title = ALLOWED_MENU_NAMES[slug]
        if not photo_msg.photo:
            return await m.reply_text("That message doesn’t contain a photo.")
        file_id = photo_msg.photo[-1].file_id
        _set_menu(slug, title, menu_text, file_id)
        await m.reply_text(f"✅ Saved menu for <b>{title}</b>.\nUse 💕 Menu → {title} to view.", disable_web_page_preview=True)
