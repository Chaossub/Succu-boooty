# handlers/menu.py
import os, time
from typing import Dict, Optional, List

from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# ---- Mongo (standalone to avoid circular imports)
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
if not MONGO_URL:
    raise RuntimeError("MONGO_URL / MONGODB_URI / MONGO_URI is required")
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]
col_model_menus = _db.get_collection("model_menus")

# ---- Admins / models
def _parse_ids(env_val: Optional[str]) -> List[int]:
    if not env_val:
        return []
    out: List[int] = []
    for tok in env_val.replace(" ", "").split(","):
        if not tok:
            continue
        try:
            out.append(int(tok))
        except ValueError:
            pass
    return out

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
SUPER_ADMINS = set(_parse_ids(os.getenv("SUPER_ADMINS")))

def _is_owner_or_admin(user_id: Optional[int]) -> bool:
    return bool(user_id) and (user_id == OWNER_ID or user_id in SUPER_ADMINS)

def _int_or_zero(s: Optional[str]) -> int:
    try:
        return int(s) if s else 0
    except ValueError:
        return 0

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
    if not name:
        return None
    k = name.strip().lower()
    if k in MODELS:
        return k
    for key, meta in MODELS.items():
        if meta["name"].lower() == k:
            return key
    return None

def _can_edit_model(user_id: int, username: Optional[str], model_key: str) -> bool:
    """Owner/Admin can edit any; a model can edit their own."""
    if _is_owner_or_admin(user_id):
        return True
    meta = MODELS.get(model_key, {})
    if not meta:
        return False
    if user_id and meta.get("uid") and user_id == meta["uid"]:
        return True
    if username and meta.get("username") and username.lower() == meta["username"]:
        return True
    return False

def _extract_args(m: Message) -> List[str]:
    if m.caption and m.caption.strip():
        return m.caption.split(maxsplit=2)
    if m.text and m.text.strip():
        return m.text.split(maxsplit=2)
    return []

def register(app: Client):

    @app.on_message(filters.command("createmenu") & filters.private)
    async def create_menu(_: Client, m: Message):
        if not m.from_user:
            return

        args = _extract_args(m)
        if len(args) < 2:
            await m.reply_text("Usage:\n`/createmenu <ModelName> <text>` (you may attach a photo)", quote=True)
            return

        model_key = _model_key_from_name(args[1])
        if not model_key:
            await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True)
            return

        if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
            await m.reply_text("⛔ You are not allowed to edit that model’s menu.", quote=True)
            return

        text = args[2] if len(args) >= 3 else ""
        photo_id = m.photo.file_id if m.photo else None

        col_model_menus.update_one(
            {"key": model_key},
            {"$set": {
                "text": text,
                "photo_id": photo_id,
                "updated_at": int(time.time())
            }},
            upsert=True
        )

        await m.reply_text(f"✅ Saved menu for **{MODELS[model_key]['name']}**.", quote=True)
