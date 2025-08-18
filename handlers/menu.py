# handlers/menu.py
# Model menus with persistence + role-limited editing.
# - UI: /menu or callback "dmf_open_menu" opens model buttons + contact row
# - Storage: data/menus.json (photo+caption OR text-only)
# - Editors:
#     * OWNER_ID, SUPER_ADMIN_ID, MENU_EDITORS -> can edit ALL
#     * A model's own Telegram ID -> can edit ONLY their model
#
# Commands:
#   /menu                       -> open menu UI
#   /addmenu <model> [text]     -> save menu (reply to photo+caption OR give text)
#   /changemenu <model>         -> same as add, but requires content (reply or text)
#   /deletemenu <model>         -> remove saved menu
#   /listmenus                  -> show which models have a saved menu
#
# Callback entries used by dm_foolproof:
#   dmf_open_menu               -> open menu UI
#   menu:view:<key>             -> show specific model menu

import os, json, pathlib
from typing import Dict, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)

# ------------------ IDs / Names from ENV ------------------

def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID        = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID  = _to_int(os.getenv("SUPER_ADMIN_ID"))

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

# Model user IDs (so they can edit their own menu)
RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))

# Extra admins who can edit all menus
_EXTRA_EDITORS = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").split(","):
        v = _to_int(tok.strip())
        if v:
            _EXTRA_EDITORS.add(v)

ADMIN_IDS = {i for i in (OWNER_ID, SUPER_ADMIN_ID) if i} | _EXTRA_EDITORS

# Model registry
MODELS = {
    "roni": {"title": RONI_NAME, "owner_id": OWNER_ID},
    "ruby": {"title": RUBY_NAME, "owner_id": RUBY_ID},
    "rin":  {"title": RIN_NAME,  "owner_id": RIN_ID},
    "savy": {"title": SAVY_NAME, "owner_id": SAVY_ID},
}

# ------------------ Persistence ------------------

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MENUS_PATH = DATA_DIR / "menus.json"

# schema:
# {
#   "roni": {"type":"photo", "file_id":"<file>", "caption":"..."},
#   "ruby": {"type":"text",  "text":"..."},
#   ...
# }
def _load_menus() -> Dict[str, dict]:
    try:
        with MENUS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_menus(data: Dict[str, dict]) -> None:
    tmp = MENUS_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(MENUS_PATH)

_MEMO: Dict[str, dict] = _load_menus()

# ------------------ Permissions ------------------

def _can_edit_any(uid: Optional[int]) -> bool:
    return bool(uid and uid in ADMIN_IDS)

def _normalize_model(s: str) -> Optional[str]:
    s = (s or "").strip().lower()
    return s if s in MODELS else None

def _can_edit_model(uid: Optional[int], key: str) -> bool:
    if _can_edit_any(uid):
        return True
    owner_id = MODELS.get(key, {}).get("owner_id")
    return bool(uid and owner_id and uid == owner_id)

# ------------------ UI builders ------------------

def _menu_root_text() -> str:
    return "Pick a model to view their menu, or contact them directly:"

def _menu_root_kb(me: Optional[str]) -> InlineKeyboardMarkup:
    # Model buttons
    rows = [
        [
            InlineKeyboardButton(MODELS["roni"]["title"], callback_data="menu:view:roni"),
            InlineKeyboardButton(MODELS["ruby"]["title"], callback_data="menu:view:ruby"),
        ],
        [
            InlineKeyboardButton(MODELS["rin"]["title"],  callback_data="menu:view:rin"),
            InlineKeyboardButton(MODELS["savy"]["title"], callback_data="menu:view:savy"),
        ],
    ]

    # Contact row (deep links to profiles by user id if present)
    contact_row = []
    for key in ("roni", "ruby", "rin", "savy"):
        uid = MODELS[key]["owner_id"]
        title = MODELS[key]["title"]
        if uid:
            contact_row.append(InlineKeyboardButton(f"💌 {title}", url=f"tg://user?id={uid}"))
    if contact_row:
        # break into two balanced rows if too long
        if len(contact_row) > 3:
            rows.append(contact_row[:2])
            rows.append(contact_row[2:])
        else:
            rows.append(contact_row)

    # Back to Start (your DM portal listens for this)
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])

    return InlineKeyboardMarkup(rows)

def _back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
    ])

# These two are imported by your DM portal
def menu_tabs_text() -> str:
    return _menu_root_text()

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return _menu_root_kb(None)

# ------------------ Helpers to render a menu ------------------

async def _send_model_menu(client: Client, chat_id: int, key: str):
    data = _MEMO.get(key)
    title = MODELS[key]["title"]
    if not data:
        await client.send_message(chat_id, f"No saved menu for {title} yet.", reply_markup=_back_to_menu_kb())
        return

    if data.get("type") == "photo" and data.get("file_id"):
        await client.send_photo(chat_id, data["file_id"], caption=data.get("caption") or f"{title}'s Menu",
                                reply_markup=_back_to_menu_kb())
    else:
        text = data.get("text") or f"{title}'s Menu"
        await client.send_message(chat_id, text, reply_markup=_back_to_menu_kb(), disable_web_page_preview=True)

def _extract_photo_and_caption(m: Message) -> Tuple[Optional[str], Optional[str]]:
    """
    When used on a replied-to message, returns (file_id, caption).
    """
    if not m.reply_to_message:
        return None, None

    rp = m.reply_to_message
    cap = (rp.caption or "").strip() or None

    if rp.photo:
        return rp.photo.file_id, cap
    # allow document images too if you ever send jpg/png as document
    if rp.document and str(rp.document.mime_type or "").startswith("image/"):
        return rp.document.file_id, cap

    return None, None

# ------------------ Register ------------------

def register(app: Client):

    # /menu (direct command)
    @app.on_message(filters.command("menu"))
    async def cmd_menu(client: Client, m: Message):
        try:
            await m.reply_text(_menu_root_text(), reply_markup=_menu_root_kb(None), disable_web_page_preview=True)
        except Exception:
            await m.reply_text("Menu is unavailable right now.", reply_markup=_back_to_menu_kb())

    # Called by your DM portal button
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(_menu_root_text(), reply_markup=_menu_root_kb(None), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(_menu_root_text(), reply_markup=_menu_root_kb(None), disable_web_page_preview=True)
        await cq.answer()

    # View specific model
    @app.on_callback_query(filters.regex(r"^menu:view:(roni|ruby|rin|savy)$"))
    async def cb_view_model(client: Client, cq: CallbackQuery):
        key = cq.data.split(":")[-1]
        await _send_model_menu(client, cq.from_user.id, key)
        await cq.answer()

    # ----- Admin/model editing -----

    def _guard_edit(m: Message, key: Optional[str]) -> Optional[str]:
        if not key:
            return "Usage: /addmenu <roni|ruby|rin|savy> [text]\n(Or reply to a photo+caption with /addmenu <model>)"
        if key not in MODELS:
            return "Unknown model. Use one of: roni, ruby, rin, savy."
        if not (_can_edit_any(m.from_user.id) or _can_edit_model(m.from_user.id, key)):
            return "You don't have permission to edit this model's menu."
        return None

    @app.on_message(filters.command("addmenu"))
    async def cmd_addmenu(client: Client, m: Message):
        args = m.command[1:] if m.command else []
        key = _normalize_model(args[0]) if args else None
        guard = _guard_edit(m, key)
        if guard:
            return await m.reply_text(guard)

        # Prefer photo from a replied message
        file_id, caption = _extract_photo_and_caption(m)

        if file_id:
            _MEMO[key] = {"type": "photo", "file_id": file_id, "caption": caption or ""}
            _save_menus(_MEMO)
            return await m.reply_text(f"{MODELS[key]['title']}'s menu saved (photo).")

        # Else, use the remainder text after the model token
        text_after = " ".join(args[1:]).strip()
        if not text_after:
            return await m.reply_text(
                "Send as either:\n"
                "• Reply to a photo (with caption) and run /addmenu <model>\n"
                "• Or: /addmenu <model> <text menu>"
            )

        _MEMO[key] = {"type": "text", "text": text_after}
        _save_menus(_MEMO)
        await m.reply_text(f"{MODELS[key]['title']}'s menu saved (text).")

    @app.on_message(filters.command("changemenu"))
    async def cmd_changemenu(client: Client, m: Message):
        args = m.command[1:] if m.command else []
        key = _normalize_model(args[0]) if args else None
        guard = _guard_edit(m, key)
        if guard:
            return await m.reply_text(guard)

        file_id, caption = _extract_photo_and_caption(m)
        if file_id:
            _MEMO[key] = {"type": "photo", "file_id": file_id, "caption": caption or ""}
            _save_menus(_MEMO)
            return await m.reply_text(f"{MODELS[key]['title']}'s menu updated (photo).")

        text_after = " ".join(args[1:]).strip()
        if not text_after:
            return await m.reply_text("Reply to a new photo OR pass new text after the model name.")
        _MEMO[key] = {"type": "text", "text": text_after}
        _save_menus(_MEMO)
        await m.reply_text(f"{MODELS[key]['title']}'s menu updated (text).")

    @app.on_message(filters.command("deletemenu"))
    async def cmd_deletemenu(client: Client, m: Message):
        args = m.command[1:] if m.command else []
        key = _normalize_model(args[0]) if args else None
        guard = _guard_edit(m, key)
        if guard:
            return await m.reply_text(guard)

        if key in _MEMO:
            _MEMO.pop(key, None)
            _save_menus(_MEMO)
            await m.reply_text(f"Deleted {MODELS[key]['title']}'s menu.")
        else:
            await m.reply_text("Nothing saved for that model.")

    @app.on_message(filters.command("listmenus"))
    async def cmd_listmenus(client: Client, m: Message):
        if not (_can_edit_any(m.from_user.id) or m.from_user.id in {v["owner_id"] for v in MODELS.values() if v["owner_id"]}):
            return await m.reply_text("Admins/models only.")
        if not _MEMO:
            return await m.reply_text("No menus saved yet.")
        lines = []
        for key in ("roni", "ruby", "rin", "savy"):
            status = "✅" if key in _MEMO else "❌"
            lines.append(f"{status} {MODELS[key]['title']}")
        await m.reply_text("<b>Saved Menus</b>\n" + "\n".join(lines), disable_web_page_preview=True)
