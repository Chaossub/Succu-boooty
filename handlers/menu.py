# handlers/menu.py
import os, time
from typing import Dict, Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# ---------- Mongo -----------
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
if not MONGO_URL:
    raise RuntimeError("MONGO_URL / MONGODB_URI / MONGO_URI is required")
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]
col_model_menus = _db.get_collection("model_menus")

# ---------- Auth / Models -----------
def _parse_ids(s: Optional[str]) -> List[int]:
    if not s: return []
    out = []
    for tok in s.replace(" ", "").split(","):
        if not tok: continue
        try: out.append(int(tok))
        except ValueError: pass
    return out

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
SUPER_ADMINS = set(_parse_ids(os.getenv("SUPER_ADMINS")))
def _is_owner_or_admin(uid: Optional[int]) -> bool:
    return bool(uid) and (uid == OWNER_ID or uid in SUPER_ADMINS)

def _int_or_zero(v: Optional[str]) -> int:
    try: return int(v) if v else 0
    except ValueError: return 0

MODELS: Dict[str, Dict] = {
    "roni": {"name": os.getenv("RONI_NAME", "Roni"),
             "username": (os.getenv("RONI_USERNAME") or "").lower(),
             "uid": _int_or_zero(os.getenv("RONI_ID"))},
    "ruby": {"name": os.getenv("RUBY_NAME", "Ruby"),
             "username": (os.getenv("RUBY_USERNAME") or "").lower(),
             "uid": _int_or_zero(os.getenv("RUBY_ID"))},
    "rin":  {"name": os.getenv("RIN_NAME", "Rin"),
             "username": (os.getenv("RIN_USERNAME") or "").lower(),
             "uid": _int_or_zero(os.getenv("RIN_ID"))},
    "savy": {"name": os.getenv("SAVY_NAME", "Savy"),
             "username": (os.getenv("SAVY_USERNAME") or "").lower(),
             "uid": _int_or_zero(os.getenv("SAVY_ID"))},
}

def _model_key_from_name(name: str) -> Optional[str]:
    if not name: return None
    k = name.strip().lower()
    if k in MODELS: return k
    for key, meta in MODELS.items():
        if meta["name"].lower() == k:
            return key
    return None

def _can_edit_model(user_id: int, username: Optional[str], model_key: str) -> bool:
    if _is_owner_or_admin(user_id):
        return True
    meta = MODELS.get(model_key, {})
    if not meta: return False
    if meta.get("uid") and user_id == meta["uid"]:
        return True
    if username and meta.get("username") and username.lower() == meta["username"]:
        return True
    return False

def _args(m: Message) -> List[str]:
    if m.caption and m.caption.strip():
        return m.caption.split(maxsplit=2)
    if m.text and m.text.strip():
        return m.text.split(maxsplit=2)
    return []

# ---------- Register ----------
def register(app: Client):

    # /createmenu <Model> <text>  [photo optional]
    @app.on_message(filters.command("createmenu"))
    async def create_menu(_: Client, m: Message):
        if not m.from_user:
            return
        a = _args(m)
        if len(a) < 2:
            await m.reply_text("Usage:\n`/createmenu <ModelName> <text>` (you can attach a photo)", quote=True)
            return

        model_key = _model_key_from_name(a[1])
        if not model_key:
            await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True)
            return

        if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
            await m.reply_text("⛔ You aren’t allowed to edit that model’s menu.", quote=True)
            return

        text = a[2] if len(a) >= 3 else ""
        photo_id = m.photo.file_id if m.photo else None

        col_model_menus.update_one(
            {"key": model_key},
            {"$set": {"text": text, "photo_id": photo_id, "updated_at": int(time.time())}},
            upsert=True
        )
        await m.reply_text(f"✅ Saved menu for **{MODELS[model_key]['name']}**.", quote=True)

    # /editmenu <Model> <new text>  [photo optional]
    @app.on_message(filters.command("editmenu"))
    async def edit_menu(_: Client, m: Message):
        if not m.from_user: return
        a = _args(m)
        if len(a) < 2:
            await m.reply_text("Usage:\n`/editmenu <ModelName> <new text>` (attach a new photo to replace it)", quote=True)
            return
        model_key = _model_key_from_name(a[1])
        if not model_key:
            await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return
        if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
            await m.reply_text("⛔ You aren’t allowed to edit that model’s menu.", quote=True); return

        updates = {"updated_at": int(time.time())}
        if len(a) >= 3: updates["text"] = a[2]
        if m.photo:      updates["photo_id"] = m.photo.file_id

        col_model_menus.update_one({"key": model_key}, {"$set": updates}, upsert=True)
        await m.reply_text(f"✅ Updated menu for **{MODELS[model_key]['name']}**.", quote=True)

    # /deletemenu <Model>
    @app.on_message(filters.command("deletemenu"))
    async def delete_menu(_: Client, m: Message):
        if not m.from_user: return
        a = _args(m)
        if len(a) < 2:
            await m.reply_text("Usage:\n`/deletemenu <ModelName>`", quote=True); return
        model_key = _model_key_from_name(a[1])
        if not model_key:
            await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return
        if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
            await m.reply_text("⛔ You aren’t allowed to delete that model’s menu.", quote=True); return

        res = col_model_menus.delete_one({"key": model_key})
        if res.deleted_count:
            await m.reply_text(f"🗑️ Deleted menu for **{MODELS[model_key]['name']}**.", quote=True)
        else:
            await m.reply_text("There was no stored menu for that model.", quote=True)

    # /viewmenu <Model>  (quick preview)
    @app.on_message(filters.command("viewmenu"))
    async def view_menu(_: Client, m: Message):
        if not m.from_user: return
        a = _args(m)
        if len(a) < 2:
            await m.reply_text("Usage:\n`/viewmenu <ModelName>`", quote=True); return
        model_key = _model_key_from_name(a[1])
        if not model_key:
            await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return
        # Allow anyone to view via command; you can tighten this if you want.

        doc = col_model_menus.find_one({"key": model_key})
        if not doc:
            await m.reply_text("No menu saved yet.", quote=True); return

        text = (doc.get("text") or "").strip() or f"{MODELS[model_key]['name']}'s menu"
        photo_id = doc.get("photo_id")
        if photo_id:
            await m.reply_photo(photo=photo_id, caption=text)
        else:
            await m.reply_text(text)
