# handlers/menu.py
# Menus for Roni, Ruby, Rin, Savy + Contact Models + Editor commands.
# Exports: menu_tabs_text(), menu_tabs_kb() for dm_foolproof to import.

import os, json, time
from typing import Optional, Set, Dict, List, Tuple
from dataclasses import dataclass

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import RPCError

# ----------------------- IDs / helpers -----------------------

def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

# Global editors (optional)
_EXTRA_ADMINS: Set[int] = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").replace(";", ",").split(","):
        v = _to_int(tok.strip())
        if v: _EXTRA_ADMINS.add(v)

ADMIN_IDS: Set[int] = set(i for i in (OWNER_ID, SUPER_ADMIN_ID) if i) | _EXTRA_ADMINS

def _is_global_admin(uid: Optional[int]) -> bool:
    return bool(uid and (uid in ADMIN_IDS))

# ----------------------- Model roster / profile links -----------------------

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))

MODELS: List[str] = ["roni", "ruby", "rin", "savy"]
DISPLAY_NAME: Dict[str, str] = {
    "roni": RONI_NAME, "ruby": RUBY_NAME, "rin": RIN_NAME, "savy": SAVY_NAME
}
PROFILE_ID: Dict[str, Optional[int]] = {
    "roni": OWNER_ID, "ruby": RUBY_ID, "rin": RIN_ID, "savy": SAVY_ID
}

def _model_editors_from_env(model_key: str) -> Set[int]:
    key = f"MENU_EDITORS_{model_key.upper()}"
    out: Set[int] = set()
    raw = os.getenv(key, "")
    for tok in raw.replace(";", ",").split(","):
        v = _to_int(tok.strip())
        if v: out.add(v)
    return out

def _is_editor(uid: Optional[int], model_key: str) -> bool:
    if _is_global_admin(uid): return True
    return bool(uid and (uid in _model_editors_from_env(model_key)))

# ----------------------- Storage: Mongo preferred, JSON fallback -----------

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB", "succubot")
MONGO_COL = os.getenv("MONGO_MENU_COLLECTION", "menus")
_JSON_FALLBACK = os.getenv("MENU_JSON_PATH", "./data/menus.json")

@dataclass
class MenuDoc:
    model: str
    photo_id: str
    caption: str
    updated_by: int
    updated_at: float

class _MongoStore:
    def __init__(self, uri: str, db: str, col: str):
        from pymongo import MongoClient
        self._cli = MongoClient(uri)
        self._col = self._cli[db][col]
        self._col.create_index("model", unique=True)

    def get(self, model: str) -> Optional[MenuDoc]:
        d = self._col.find_one({"model": model})
        if not d: return None
        return MenuDoc(model=d["model"], photo_id=d["photo_id"], caption=d.get("caption",""),
                       updated_by=d.get("updated_by", 0), updated_at=float(d.get("updated_at", time.time())))

    def set(self, md: MenuDoc) -> None:
        self._col.update_one({"model": md.model},
                             {"$set": {"photo_id": md.photo_id, "caption": md.caption,
                                       "updated_by": md.updated_by, "updated_at": md.updated_at}},
                             upsert=True)

    def delete(self, model: str) -> bool:
        return self._col.delete_one({"model": model}).deleted_count > 0

    def list_models_with_menu(self) -> List[str]:
        return [d["model"] for d in self._col.find({}, {"model": 1})]

class _JsonStore:
    def __init__(self, path: str):
        self.path = path
        d = os.path.dirname(path)
        if d: os.makedirs(d, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f: json.dump({}, f)

    def _load(self) -> Dict[str, Dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f: return json.load(f) or {}
        except Exception:
            return {}

    def _save(self, data: Dict[str, Dict]):
        with open(self.path, "w", encoding="utf-8") as f: json.dump(data, f)

    def get(self, model: str) -> Optional[MenuDoc]:
        d = self._load().get(model)
        if not d: return None
        return MenuDoc(model=model, photo_id=d["photo_id"], caption=d.get("caption",""),
                       updated_by=d.get("updated_by", 0), updated_at=float(d.get("updated_at", time.time())))

    def set(self, md: MenuDoc) -> None:
        data = self._load()
        data[md.model] = {"photo_id": md.photo_id, "caption": md.caption,
                          "updated_by": md.updated_by, "updated_at": md.updated_at}
        self._save(data)

    def delete(self, model: str) -> bool:
        data = self._load()
        if model in data:
            data.pop(model)
            self._save(data)
            return True
        return False

    def list_models_with_menu(self) -> List[str]:
        return list(self._load().keys())

_STORE = _MongoStore(MONGO_URI, MONGO_DB, MONGO_COL) if MONGO_URI else _JsonStore(_JSON_FALLBACK)

# ----------------------- UI builders / exports -----------------------------

def _menu_panel_text() -> str:
    return "📜 <b>Model Menus</b>\nPick a model to view their current menu, or contact them directly."

def _menu_panel_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for k in MODELS:
        row.append(InlineKeyboardButton(DISPLAY_NAME.get(k, k.capitalize()), callback_data=f"menu:show:{k}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("💌 Contact Models", callback_data="menu:contact")])
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for k in MODELS:
        uid = PROFILE_ID.get(k)
        label = f"💌 {DISPLAY_NAME.get(k, k.capitalize())}"
        if uid:
            row.append(InlineKeyboardButton(label, url=f"tg://user?id={uid}"))
        else:
            row.append(InlineKeyboardButton(f"{label} (unavailable)", callback_data="menu:nop"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)

# Exported for dm_foolproof
def menu_tabs_text() -> str:
    return _menu_panel_text()

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return _menu_panel_kb()

def _norm_model(tok: Optional[str]) -> Optional[str]:
    if not tok: return None
    t = tok.strip().lower()
    return t if t in MODELS else None

def _need_photo_from(m: Message) -> Optional[Tuple[str, str]]:
    src = m
    if not getattr(src, "photo", None) and m.reply_to_message:
        src = m.reply_to_message
    if getattr(src, "photo", None):
        photo_id = src.photo.file_id
        caption  = src.caption or m.caption or ""
        return (photo_id, caption)
    return None

async def _send_menu_for(client: Client, chat_id: int, model: str):
    doc = _STORE.get(model)
    name = DISPLAY_NAME.get(model, model.capitalize())
    if not doc:
        return await client.send_message(chat_id, f"❌ No menu saved yet for <b>{name}</b>.")
    try:
        await client.send_photo(chat_id, doc.photo_id, caption=doc.caption or f"{name} — (no caption)")
    except RPCError:
        await client.send_message(chat_id, f"📜 <b>{name}</b>\n\n{doc.caption or '(no caption)'}")

# ----------------------- Register -----------------------------

def register(app: Client):
    # Open menu panel (works in groups and DMs)
    @app.on_message(filters.command("menu"))
    async def open_menu_panel(client: Client, m: Message):
        await m.reply_text(_menu_panel_text(), reply_markup=_menu_panel_kb(), disable_web_page_preview=True)

    # Shortcut: /menu <model> in DMs shows that model directly
    @app.on_message(filters.private & filters.command("menu"))
    async def direct_show_if_arg(client: Client, m: Message):
        if len(m.command) >= 2:
            model = _norm_model(m.command[1])
            if model:
                await _send_menu_for(client, m.chat.id, model)

    # Callback: show a model's menu
    @app.on_callback_query(filters.regex(r"^menu:show:(?P<model>[a-z0-9_]+)$"))
    async def cb_show_menu(client: Client, cq: CallbackQuery):
        model = _norm_model(cq.matches[0].group("model"))
        if not model:
            return await cq.answer("Unknown model.", show_alert=True)
        try: await cq.answer()
        except Exception: pass
        await _send_menu_for(client, cq.from_user.id, model)

    # Callback: contact models panel
    @app.on_callback_query(filters.regex(r"^menu:contact$"))
    async def cb_contact_models(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💌 <b>Contact Models</b>\nTap a name to open DM:",
                                       reply_markup=_contact_models_kb(),
                                       disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("💌 <b>Contact Models</b>\nTap a name to open DM:",
                                        reply_markup=_contact_models_kb(),
                                        disable_web_page_preview=True)
        await cq.answer()

    # Callback: back to menu home
    @app.on_callback_query(filters.regex(r"^menu:home$"))
    async def cb_menu_home(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(_menu_panel_text(), reply_markup=_menu_panel_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(_menu_panel_text(), reply_markup=_menu_panel_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:nop$"))
    async def cb_menu_nop(client: Client, cq: CallbackQuery):
        await cq.answer("That profile link isn’t configured yet.", show_alert=True)

    # ---------------- Editor Commands ----------------

    @app.on_message(filters.command("listmenus"))
    async def list_menus(client: Client, m: Message):
        have = set(_STORE.list_models_with_menu())
        if not have:
            return await m.reply_text("No menus saved yet.")
        lines = []
        for k in MODELS:
            mark = "✅" if k in have else "—"
            lines.append(f"{mark} {DISPLAY_NAME.get(k, k.capitalize())}")
        await m.reply_text("<b>Menus:</b>\n" + "\n".join(lines))

    @app.on_message(filters.command("addmenu"))
    async def add_menu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/addmenu &lt;model&gt;</code> (attach or reply to a photo)")
        model = _norm_model(m.command[1])
        if not model:
            return await m.reply_text(f"Model not recognized. Valid: {', '.join(MODELS)}")
        if not _is_editor(m.from_user.id, model):
            return await m.reply_text("Admins/authorized editors only.")
        pc = _need_photo_from(m)
        if not pc:
            return await m.reply_text("Attach or reply to a <b>photo</b> for the menu.")
        photo_id, caption = pc
        _STORE.set(MenuDoc(model=model, photo_id=photo_id, caption=caption or "", updated_by=m.from_user.id, updated_at=time.time()))
        await m.reply_text(f"✅ Saved <b>{DISPLAY_NAME.get(model, model.capitalize())}</b> menu.")

    @app.on_message(filters.command("changemenu"))
    async def change_menu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/changemenu &lt;model&gt;</code> (reply to a new photo; optional caption)")
        model = _norm_model(m.command[1])
        if not model:
            return await m.reply_text(f"Model not recognized. Valid: {', '.join(MODELS)}")
        if not _is_editor(m.from_user.id, model):
            return await m.reply_text("Admins/authorized editors only.")
        prev = _STORE.get(model)
        pc = _need_photo_from(m)
        if not pc:
            return await m.reply_text("Reply to a <b>photo</b> (new image).")
        photo_id, new_caption = pc
        caption = (new_caption if (new_caption and new_caption.strip()) else (prev.caption if prev else ""))
        _STORE.set(MenuDoc(model=model, photo_id=photo_id, caption=caption, updated_by=m.from_user.id, updated_at=time.time()))
        await m.reply_text(f"✅ Updated <b>{DISPLAY_NAME.get(model, model.capitalize())}</b> menu.")

    @app.on_message(filters.command("deletemenu"))
    async def delete_menu(client: Client, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("Usage: <code>/deletemenu &lt;model&gt;</code>")
        model = _norm_model(m.command[1])
        if not model:
            return await m.reply_text(f"Model not recognized. Valid: {', '.join(MODELS)}")
        if not _is_editor(m.from_user.id, model):
            return await m.reply_text("Admins/authorized editors only.")
        ok = _STORE.delete(model)
        await m.reply_text(("✅ Deleted" if ok else "Nothing to delete for") + f" <b>{DISPLAY_NAME.get(model, model.capitalize())}</b>.")
