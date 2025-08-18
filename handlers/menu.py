# handlers/menu.py
# Simple, self-contained Menus handler with storage + role-gated editing.
# Commands:
#   /menu                         -> Open menu picker (Roni, Ruby, Rin, Savy + Contact Models)
#   /addmenu <model>              -> (reply to a PHOTO or send a PHOTO with caption)
#   /changemenu <model>           -> (reply to a PHOTO or send a PHOTO with caption)
#   /deletemenu <model>           -> Delete a model's menu
#   /listmenus                    -> List which models have menus
# Callbacks:
#   menu:show:<model>             -> Show a model's menu (photo + caption)
#   menu:contact                  -> Contact Models panel (DM links)

import os, json, pathlib
from typing import Dict, Optional, Set, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)

# ---------- Models we support ----------
MODELS = ["roni", "ruby", "rin", "savy"]

# ---------- Env helpers ----------
def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

def _ids_from_env(name: str) -> Set[int]:
    raw = os.getenv(name, "")
    ids: Set[int] = set()
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            ids.add(int(tok))
    return ids

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))
GLOBAL_EDITORS = _ids_from_env("MENU_EDITORS")  # comma/semicolon-separated Telegram user IDs

# Per-model editor lists (optional)
EDIT_RONI = _ids_from_env("MENU_EDITORS_RONI")
EDIT_RUBY = _ids_from_env("MENU_EDITORS_RUBY")
EDIT_RIN  = _ids_from_env("MENU_EDITORS_RIN")
EDIT_SAVY = _ids_from_env("MENU_EDITORS_SAVY")

# DM deep links (optional, used in "Contact Models")
RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))

# ---------- Storage (JSON file by default) ----------
MENU_JSON_PATH = os.getenv("MENU_JSON_PATH", "./data/menus.json")

def _ensure_dir(path: str) -> None:
    p = pathlib.Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

def _load_storage() -> Dict[str, Dict[str, str]]:
    try:
        with open(MENU_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # expected: { "roni": {"photo": "<file_id>", "caption": "text"}, ... }
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}

def _save_storage(data: Dict[str, Dict[str, str]]) -> None:
    _ensure_dir(MENU_JSON_PATH)
    with open(MENU_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Permissions ----------
def _per_model_editors(model: str) -> Set[int]:
    model = model.lower()
    if model == "roni": return EDIT_RONI
    if model == "ruby": return EDIT_RUBY
    if model == "rin":  return EDIT_RIN
    if model == "savy": return EDIT_SAVY
    return set()

def _is_editor(user_id: Optional[int], model: Optional[str] = None) -> bool:
    if not user_id:
        return False
    if user_id == OWNER_ID or user_id == SUPER_ADMIN_ID:
        return True
    if user_id in GLOBAL_EDITORS:
        return True
    if model:
        if user_id in _per_model_editors(model):
            return True
    return False

# ---------- Keyboards ----------
def _menu_root_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Roni", callback_data="menu:show:roni"),
         InlineKeyboardButton("Ruby", callback_data="menu:show:ruby")],
        [InlineKeyboardButton("Rin",  callback_data="menu:show:rin"),
         InlineKeyboardButton("Savy", callback_data="menu:show:savy")],
        [InlineKeyboardButton("💌 Contact Models", callback_data="menu:contact")]
    ]
    # add “Back to Start” if your DM portal is installed
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _contact_models_kb() -> InlineKeyboardMarkup:
    row1 = []
    if OWNER_ID: row1.append(InlineKeyboardButton("💌 Roni", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID:  row1.append(InlineKeyboardButton("💌 Ruby", url=f"tg://user?id={RUBY_ID}"))
    rows = []
    if row1: rows.append(row1)
    row2 = []
    if RIN_ID:  row2.append(InlineKeyboardButton("💌 Rin",  url=f"tg://user?id={RIN_ID}"))
    if SAVY_ID: row2.append(InlineKeyboardButton("💌 Savy", url=f"tg://user?id={SAVY_ID}"))
    if row2: rows.append(row2)
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

# ---------- Utilities ----------
def _get_photo_and_caption_from_message(m: Message) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (photo_file_id, caption) from either the message itself (if it has a photo),
    or the replied-to message (if present and has a photo).
    """
    # original message
    if m.photo:
        file_id = m.photo.file_id
        caption = (m.caption or "").strip()
        return file_id, caption

    # replied-to message
    if m.reply_to_message and m.reply_to_message.photo:
        file_id = m.reply_to_message.photo.file_id
        caption = (m.reply_to_message.caption or "").strip()
        return file_id, caption

    return None, None

def _normalize_model(arg: Optional[str]) -> Optional[str]:
    if not arg:
        return None
    val = arg.strip().lower()
    return val if val in MODELS else None

async def _send_menu_for_model(client: Client, chat_id: int, model: str, store: Dict[str, Dict[str, str]]):
    rec = store.get(model)
    if not rec:
        await client.send_message(chat_id, f"❌ No menu saved for {model.title()} yet.")
        return
    photo = rec.get("photo")
    caption = rec.get("caption", "") or " "
    if photo:
        await client.send_photo(chat_id, photo, caption=caption)
    else:
        await client.send_message(chat_id, caption or f"{model.title()} menu (no photo)")

# ---------- Register ----------
def register(app: Client):

    # /menu - works in both groups and DMs
    @app.on_message(filters.command("menu"))
    async def cmd_menu(client: Client, m: Message):
        await m.reply_text(
            "📖 <b>Model Menus</b>\nPick a model or contact directly:",
            reply_markup=_menu_root_kb(),
            disable_web_page_preview=True
        )

    # Add a menu (reply/send a PHOTO with optional caption)
    @app.on_message(filters.command("addmenu"))
    async def cmd_addmenu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/addmenu roni|ruby|rin|savy</code> (reply/send a PHOTO with caption)")
        model = _normalize_model(m.command[1])
        if not model:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")

        if not _is_editor(m.from_user.id if m.from_user else None, model):
            return await m.reply_text("Admins/authorized editors only.")

        file_id, caption = _get_photo_and_caption_from_message(m)
        if not file_id:
            return await m.reply_text("Please reply to a PHOTO or send a PHOTO with the command.")
        store = _load_storage()
        store[model] = {"photo": file_id, "caption": caption or ""}
        _save_storage(store)
        await m.reply_text(f"✅ Saved menu for <b>{model.title()}</b>.")

    # Change a menu (reply/send a new PHOTO; caption optional to overwrite)
    @app.on_message(filters.command("changemenu"))
    async def cmd_changemenu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/changemenu roni|ruby|rin|savy</code> (reply/send a PHOTO)")
        model = _normalize_model(m.command[1])
        if not model:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")

        if not _is_editor(m.from_user.id if m.from_user else None, model):
            return await m.reply_text("Admins/authorized editors only.")

        file_id, caption = _get_photo_and_caption_from_message(m)
        if not file_id:
            return await m.reply_text("Please reply to a PHOTO or send a PHOTO with the command.")

        store = _load_storage()
        prev = store.get(model, {})
        # keep old caption if new photo has no caption
        if caption is None or caption.strip() == "":
            caption = prev.get("caption", "")
        store[model] = {"photo": file_id, "caption": caption or ""}
        _save_storage(store)
        await m.reply_text(f"✅ Updated menu for <b>{model.title()}</b>.")

    # Delete a menu
    @app.on_message(filters.command("deletemenu"))
    async def cmd_deletemenu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/deletemenu roni|ruby|rin|savy</code>")
        model = _normalize_model(m.command[1])
        if not model:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")

        if not _is_editor(m.from_user.id if m.from_user else None, model):
            return await m.reply_text("Admins/authorized editors only.")

        store = _load_storage()
        if model in store:
            store.pop(model, None)
            _save_storage(store)
            return await m.reply_text(f"🗑️ Deleted menu for <b>{model.title()}</b>.")
        return await m.reply_text(f"Nothing to delete — no menu saved for <b>{model.title()}</b>.")

    # List menus present
    @app.on_message(filters.command("listmenus"))
    async def cmd_listmenus(client: Client, m: Message):
        store = _load_storage()
        have = [k for k in MODELS if k in store]
        if not have:
            return await m.reply_text("No menus saved yet.")
        pretty = ", ".join(x.title() for x in have)
        await m.reply_text(f"✅ Menus saved for: {pretty}")

    # Optional: view a single model menu by command
    @app.on_message(filters.command("viewmenu"))
    async def cmd_viewmenu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/viewmenu roni|ruby|rin|savy</code>")
        model = _normalize_model(m.command[1])
        if not model:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")
        store = _load_storage()
        await _send_menu_for_model(client, m.chat.id, model, store)

    # Callbacks: show menu image/caption
    @app.on_callback_query(filters.regex(r"^menu:show:(roni|ruby|rin|savy)$"))
    async def cb_show_model(client: Client, cq: CallbackQuery):
        model = cq.data.split(":")[-1]
        store = _load_storage()

        rec = store.get(model)
        if not rec:
            await cq.answer("No menu saved yet for this model.", show_alert=True)
            try:
                await cq.message.edit_text("Menu is unavailable right now.", reply_markup=_menu_root_kb())
            except Exception:
                await cq.message.reply_text("Menu is unavailable right now.", reply_markup=_menu_root_kb())
            return

        photo = rec.get("photo")
        caption = rec.get("caption", "") or " "
        # Try to edit in place to keep the same message thread tidy:
        try:
            if cq.message.photo and cq.message.media_group_id is None:
                # Replace photo + caption
                await cq.message.edit_media(InputMediaPhoto(media=photo, caption=caption))
                await cq.message.edit_reply_markup(reply_markup=_menu_root_kb())
            else:
                # Send fresh if current message isn't a photo
                await cq.message.reply_photo(photo, caption=caption, reply_markup=_menu_root_kb())
        except Exception:
            # Fallback to sending a fresh message
            try:
                await cq.message.reply_photo(photo, caption=caption, reply_markup=_menu_root_kb())
            except Exception:
                await cq.message.reply_text(caption, reply_markup=_menu_root_kb())

        await cq.answer()

    # Callbacks: Contact Models (DM links)
    @app.on_callback_query(filters.regex(r"^menu:contact$"))
    async def cb_contact_models(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "💌 Contact a model directly:",
                reply_markup=_contact_models_kb(),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.message.reply_text(
                "💌 Contact a model directly:",
                reply_markup=_contact_models_kb(),
                disable_web_page_preview=True
            )
        await cq.answer()
