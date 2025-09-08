# handlers/menu.py
import os, time
from typing import Dict, Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# ───── Mongo ─────
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
if not MONGO_URL:
    raise RuntimeError("MONGO_URL / MONGODB_URI / MONGO_URI is required")
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]
col_model_menus = _db.get_collection("model_menus")

# ───── Models & Admins ─────
def _int_or_zero(v: Optional[str]) -> int:
    try: return int(v) if v else 0
    except ValueError: return 0

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
SUPER_ADMINS = {int(x) for x in (os.getenv("SUPER_ADMINS") or "").replace(" ", "").split(",") if x}

MODELS: Dict[str, Dict] = {
    "roni": {"name": os.getenv("RONI_NAME", "Roni"), "uid": _int_or_zero(os.getenv("RONI_ID"))},
    "ruby": {"name": os.getenv("RUBY_NAME", "Ruby"), "uid": _int_or_zero(os.getenv("RUBY_ID"))},
    "rin":  {"name": os.getenv("RIN_NAME", "Rin"), "uid": _int_or_zero(os.getenv("RIN_ID"))},
    "savy": {"name": os.getenv("SAVY_NAME", "Savy"), "uid": _int_or_zero(os.getenv("SAVY_ID"))},
}

def _model_key_from_name(name: str) -> Optional[str]:
    if not name: return None
    k = name.strip().lower()
    if k in MODELS: return k
    for key, meta in MODELS.items():
        if meta["name"].lower() == k: return key
    return None

def _can_edit(user_id: int, model_key: str) -> bool:
    if user_id == OWNER_ID or user_id in SUPER_ADMINS:
        return True
    meta = MODELS.get(model_key)
    return bool(meta and meta.get("uid") and meta["uid"] == user_id)

def _split_args(m: Message) -> List[str]:
    if m.photo and m.caption: return m.caption.split(maxsplit=2)
    if m.text: return m.text.split(maxsplit=2)
    if m.caption: return m.caption.split(maxsplit=2)
    return []

# ───── Register ─────
def register(app: Client):

    @app.on_message(filters.command("createmenu"))
    async def createmenu(_: Client, m: Message):
        args = _split_args(m)
        if len(args) < 2:
            await m.reply_text("Usage:\n/createmenu <Model> <text>", quote=True); return

        model_key = _model_key_from_name(args[1])
        if not model_key:
            await m.reply_text("❌ Unknown model. Use Roni, Ruby, Rin, or Savy.", quote=True); return
        if not _can_edit(m.from_user.id, model_key):
            await m.reply_text("⛔ You aren’t allowed to edit that model’s menu.", quote=True); return

        text = args[2] if len(args) >= 3 else (m.caption or "")
        photo_id = m.photo.file_id if m.photo else None

        col_model_menus.update_one(
            {"key": model_key},
            {"$set": {"text": text, "photo_id": photo_id, "updated_at": int(time.time())}},
            upsert=True
        )
        await m.reply_text(f"✅ Saved menu for **{MODELS[model_key]['name']}**.\n\n{text or '(no text)'}")

    @app.on_message(filters.command("viewmenu"))
    async def viewmenu(_: Client, m: Message):
        args = _split_args(m)
        if len(args) < 2:
            await m.reply_text("Usage:\n/viewmenu <Model>", quote=True); return

        model_key = _model_key_from_name(args[1])
        if not model_key:
            await m.reply_text("❌ Unknown model. Use Roni, Ruby, Rin, or Savy.", quote=True); return

        doc = col_model_menus.find_one({"key": model_key})
        if not doc:
            await m.reply_text("⚠️ No menu saved yet.", quote=True); return

        text = (doc.get("text") or "").strip() or f"{MODELS[model_key]['name']}'s menu"
        if doc.get("photo_id"):
            await m.reply_photo(photo=doc["photo_id"], caption=text)
        else:
            await m.reply_text(text)
