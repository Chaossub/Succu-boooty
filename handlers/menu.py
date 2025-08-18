# handlers/menu.py
import os, json, time
from typing import Dict, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
)

# ---------- ENV / IDs ----------
def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        if x is None or x == "" or x == "None":
            return None
        return int(str(x).strip())
    except Exception:
        return None

OWNER_ID        = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID  = _to_int(os.getenv("SUPER_ADMIN_ID"))

RONI_ID         = _to_int(os.getenv("RUBY_ID"))  # NOTE: keep your envs — adjust if needed
RUBY_ID         = _to_int(os.getenv("RUBY_ID"))
RIN_ID          = _to_int(os.getenv("RIN_ID"))
SAVY_ID         = _to_int(os.getenv("SAVY_ID"))

RONI_NAME       = os.getenv("RONI_NAME", "Roni")
RUBY_NAME       = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME        = os.getenv("RIN_NAME", "Rin")
SAVY_NAME       = os.getenv("SAVY_NAME", "Savy")

# Contact IDs default to any configured values
CONTACT_IDS = {
    "roni": _to_int(os.getenv("OWNER_ID")) or RONI_ID,
    "ruby": RUBY_ID,
    "rin":  RIN_ID,
    "savy": SAVY_ID,
}

# Models map (keys are normalized)
MODELS: Dict[str, Dict[str, Optional[int]]] = {
    "roni": {"label": RONI_NAME, "uid": CONTACT_IDS["roni"]},
    "ruby": {"label": RUBY_NAME, "uid": CONTACT_IDS["ruby"]},
    "rin":  {"label": RIN_NAME,  "uid": CONTACT_IDS["rin"]},
    "savy": {"label": SAVY_NAME, "uid": CONTACT_IDS["savy"]},
}

# Extra editors (comma-separated user IDs)
_EXTRA_EDITORS = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").split(","):
        try:
            v = int(tok.strip())
            _EXTRA_EDITORS.add(v)
        except Exception:
            pass

# ---------- STORAGE ----------
MENUS_FILE = os.getenv("MENUS_FILE", os.path.join("data", "menus.json"))

def _ensure_store():
    base = os.path.dirname(MENUS_FILE)
    if base and not os.path.exists(base):
        os.makedirs(base, exist_ok=True)
    if not os.path.exists(MENUS_FILE):
        with open(MENUS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def _load() -> Dict[str, dict]:
    _ensure_store()
    try:
        with open(MENUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(data: Dict[str, dict]) -> None:
    _ensure_store()
    tmp = MENUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MENUS_FILE)

# ---------- PERMISSIONS ----------
def _is_global_admin(uid: Optional[int]) -> bool:
    return bool(uid and (uid == OWNER_ID or uid == SUPER_ADMIN_ID or uid in _EXTRA_EDITORS))

def _editor_for(model_key: str) -> Optional[int]:
    # model’s own account may edit their own menu
    return MODELS.get(model_key, {}).get("uid")

def _can_edit(uid: Optional[int], model_key: str) -> bool:
    if _is_global_admin(uid):
        return True
    model_uid = _editor_for(model_key)
    return bool(uid and model_uid and uid == model_uid)

# ---------- UI ----------
def _root_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"{MODELS['roni']['label']}", callback_data="menu:view:roni"),
            InlineKeyboardButton(f"{MODELS['ruby']['label']}", callback_data="menu:view:ruby"),
        ],
        [
            InlineKeyboardButton(f"{MODELS['rin']['label']}",  callback_data="menu:view:rin"),
            InlineKeyboardButton(f"{MODELS['savy']['label']}", callback_data="menu:view:savy"),
        ],
        [InlineKeyboardButton("💌 Contact Models", callback_data="menu:contact")],
        [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for k in ["roni", "ruby", "rin", "savy"]:
        uid = MODELS[k]["uid"]
        if uid:
            row.append(InlineKeyboardButton(f"💌 {MODELS[k]['label']}", url=f"tg://user?id={uid}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")])
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def menu_tabs_text() -> str:
    return "Choose a model to view their menu:"

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return _root_kb()

# ---------- Helpers ----------
def _normalize_model(arg: Optional[str]) -> Optional[str]:
    if not arg:
        return None
    a = arg.strip().lower()
    # allow friendly names/aliases
    aliases = {
        "roni": "roni", "ronnie": "roni",
        "ruby": "ruby",
        "rin": "rin",
        "savy": "savy", "sav": "savy", "savage": "savy",
    }
    return aliases.get(a)

def _parse_add_args(m: Message) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # returns (model_key, text_caption, photo_id)
    cmd = m.text or m.caption or ""
    parts = cmd.split(maxsplit=2)  # /addmenu <model> <text...>
    model_key = _normalize_model(parts[1] if len(parts) > 1 else None)

    text_caption = None
    if len(parts) > 2:
        text_caption = parts[2].strip()

    photo_id = None
    if m.reply_to_message and m.reply_to_message.photo:
        photo_id = m.reply_to_message.photo.file_id
        # if you replied to a photo and did NOT pass text, use your command message text (without command and model)
        if not text_caption:
            text_caption = (m.text or m.caption or "").split(maxsplit=2)[2] if len(parts) > 2 else None

    return model_key, text_caption, photo_id

# ---------- Register ----------
def register(app: Client):

    # Open Menu (from welcome)
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb())
        except Exception:
            await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb())
        await cq.answer()

    # Contact Models
    @app.on_callback_query(filters.regex(r"^menu:contact$"))
    async def cb_contact(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("Contact a model directly:", reply_markup=_contact_kb())
        except Exception:
            await cq.message.reply_text("Contact a model directly:", reply_markup=_contact_kb())
        await cq.answer()

    # View menu
    @app.on_callback_query(filters.regex(r"^menu:view:(roni|ruby|rin|savy)$"))
    async def cb_view_menu(client: Client, cq: CallbackQuery):
        model_key = cq.data.rsplit(":", 1)[1]
        data = _load()
        entry = data.get(model_key)
        nav = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")],
            [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
        ])
        if not entry:
            try:
                await cq.message.edit_text(f"No saved menu for {MODELS[model_key]['label']} yet.", reply_markup=nav)
            except Exception:
                await cq.message.reply_text(f"No saved menu for {MODELS[model_key]['label']} yet.", reply_markup=nav)
            return await cq.answer()

        text = entry.get("text") or " "
        photo_id = entry.get("photo_id")
        if photo_id:
            # send photo to chat to avoid editing media collisions
            try:
                await client.send_photo(cq.from_user.id, photo_id, caption=text, reply_markup=nav)
            except Exception:
                # fall back to text
                await cq.message.edit_text(text, reply_markup=nav, disable_web_page_preview=True)
        else:
            try:
                await cq.message.edit_text(text, reply_markup=nav, disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(text, reply_markup=nav, disable_web_page_preview=True)
        await cq.answer()

    # ---------- Commands for editors ----------

    @app.on_message(filters.command("listmenus"))
    async def listmenus(client: Client, m: Message):
        data = _load()
        if not data:
            return await m.reply_text("No menus saved yet.")
        lines = []
        for k, v in data.items():
            who = MODELS.get(k, {}).get("label", k.title())
            has_pic = "📷" if v.get("photo_id") else "—"
            lines.append(f"• {who}: {('%.40s' % (v.get('text') or '')).strip()} {has_pic}")
        await m.reply_text("\n".join(lines))

    @app.on_message(filters.command("addmenu"))
    async def addmenu(client: Client, m: Message):
        model_key, text_caption, photo_id = _parse_add_args(m)
        if not model_key:
            return await m.reply_text("Usage: <code>/addmenu &lt;roni|ruby|rin|savy&gt; &lt;text...&gt;</code>\n"
                                      "Tip: Reply to a photo to set/replace the header image.", disable_web_page_preview=True)
        if not _can_edit(m.from_user.id if m.from_user else None, model_key):
            return await m.reply_text("You can’t edit that model’s menu.")

        # If no text provided but this message itself carries text (e.g., long caption), use it
        if not text_caption:
            # pull full message (minus '/addmenu model')
            raw = m.text or m.caption or ""
            parts = raw.split(maxsplit=2)
            text_caption = parts[2].strip() if len(parts) > 2 else None

        if not text_caption and not photo_id:
            return await m.reply_text("Nothing to save. Provide text after the command, or reply to a photo.")

        data = _load()
        data[model_key] = {
            "text": text_caption or data.get(model_key, {}).get("text"),
            "photo_id": photo_id or data.get(model_key, {}).get("photo_id"),
            "updated_at": int(time.time()),
        }
        _save(data)
        await m.reply_text(f"Saved menu for {MODELS[model_key]['label']} ✅")

    @app.on_message(filters.command("changemenu"))
    async def changemenu(client: Client, m: Message):
        model_key, text_caption, photo_id = _parse_add_args(m)
        if not model_key:
            return await m.reply_text("Usage: <code>/changemenu &lt;roni|ruby|rin|savy&gt; [new text]</code>\n"
                                      "Reply to a photo to change the image.", disable_web_page_preview=True)
        if not _can_edit(m.from_user.id if m.from_user else None, model_key):
            return await m.reply_text("You can’t edit that model’s menu.")

        data = _load()
        if model_key not in data:
            data[model_key] = {"text": None, "photo_id": None, "updated_at": int(time.time())}

        if text_caption is not None:
            data[model_key]["text"] = text_caption
        if photo_id is not None:
            data[model_key]["photo_id"] = photo_id
        data[model_key]["updated_at"] = int(time.time())
        _save(data)
        await m.reply_text(f"Updated menu for {MODELS[model_key]['label']} ✅")

    @app.on_message(filters.command("deletemenu"))
    async def deletemenu(client: Client, m: Message):
        parts = (m.text or "").split(maxsplit=1)
        model_key = _normalize_model(parts[1] if len(parts) > 1 else None)
        if not model_key:
            return await m.reply_text("Usage: <code>/deletemenu &lt;roni|ruby|rin|savy&gt;</code>", disable_web_page_preview=True)
        if not _can_edit(m.from_user.id if m.from_user else None, model_key):
            return await m.reply_text("You can’t edit that model’s menu.")
        data = _load()
        if data.pop(model_key, None) is None:
            return await m.reply_text("Nothing to delete.")
        _save(data)
        await m.reply_text(f"Deleted menu for {MODELS[model_key]['label']} ✅")
