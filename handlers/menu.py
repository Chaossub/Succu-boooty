import os, time, traceback
from typing import Dict, Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient, errors as _pm_errors
from pymongo.collection import Collection

# ───────────────── Mongo — persistent storage ─────────────────
def _mongo_url() -> Optional[str]:
    return os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

def _mongo_dbname() -> str:
    return os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"

_MONGO_URL = _mongo_url()
if not _MONGO_URL:
    raise RuntimeError("Set one of MONGO_URL / MONGODB_URI / MONGO_URI")

try:
    _mcli = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=10000)
    # Trigger server selection now to fail fast if misconfigured
    _mcli.admin.command("ping")
except Exception as e:
    raise RuntimeError(f"Mongo connection failed: {e}")

_db = _mcli[_mongo_dbname()]
col_model_menus: Collection = _db.get_collection("model_menus")
# Ensure 1 doc per model key
try:
    col_model_menus.create_index("key", unique=True, name="uniq_model_key")
except Exception:
    pass

# ──────────────── Auth & Models ────────────────
def _parse_ids(s: Optional[str]) -> List[int]:
    if not s: return []
    out: List[int] = []
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
    # Owner/Admin ⇒ any model
    if _is_owner_or_admin(user_id): return True
    # Model self-edit by uid or username
    meta = MODELS.get(model_key) or {}
    if not meta: return False
    if meta.get("uid") and user_id == meta["uid"]: return True
    if username and meta.get("username") and username.lower() == meta["username"]: return True
    return False

def _split_args(m: Message) -> List[str]:
    """
    Return ['/cmd','Model','rest of text'] from text OR caption.
    Prefer caption when a photo is attached (Telegram puts the command there).
    """
    if m.photo and m.caption: return m.caption.split(maxsplit=2)
    if m.text: return m.text.split(maxsplit=2)
    if m.caption: return m.caption.split(maxsplit=2)
    return []

# ───────────────── Helpers ─────────────────
async def _reply_err(m: Message, err: Exception, where: str):
    msg = f"⛔ Error in {where}:\n`{type(err).__name__}: {err}`"
    try:
        await m.reply_text(msg, quote=True)
    except Exception:
        # swallow
        pass

# ───────────────── Register ─────────────────
def register(app: Client):

    # /createmenu <Model> <text>   (photo optional)
    @app.on_message(filters.command("createmenu"))
    async def createmenu(_: Client, m: Message):
        try:
            if not m.from_user: return

            args = _split_args(m)
            if len(args) < 2:
                await m.reply_text("Usage:\n`/createmenu <ModelName> <text>` (you may attach a photo)", quote=True)
                return

            model_key = _model_key_from_name(args[1])
            if not model_key:
                await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True)
                return

            if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
                await m.reply_text("⛔ You aren’t allowed to edit that model’s menu.", quote=True)
                return

            text = args[2] if len(args) >= 3 else (m.caption or "")
            photo_id = m.photo.file_id if m.photo else None

            col_model_menus.update_one(
                {"key": model_key},
                {"$set": {"text": text, "photo_id": photo_id, "updated_at": int(time.time())}},
                upsert=True
            )

            await m.reply_text(f"✅ Saved menu for **{MODELS[model_key]['name']}**.\n\n{text or '(no text)'}", quote=True)

        except Exception as e:
            await _reply_err(m, e, "createmenu")

    # /editmenu <Model> <new text>   (photo optional to replace)
    @app.on_message(filters.command("editmenu"))
    async def editmenu(_: Client, m: Message):
        try:
            if not m.from_user: return
            args = _split_args(m)
            if len(args) < 2:
                await m.reply_text("Usage:\n`/editmenu <ModelName> <new text>` (attach new photo to replace)", quote=True)
                return

            model_key = _model_key_from_name(args[1])
            if not model_key:
                await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return
            if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
                await m.reply_text("⛔ You aren’t allowed to edit that model’s menu.", quote=True); return

            updates = {"updated_at": int(time.time())}
            if len(args) >= 3: updates["text"] = args[2]
            else:              updates["text"] = m.caption or ""
            if m.photo:        updates["photo_id"] = m.photo.file_id

            col_model_menus.update_one({"key": model_key}, {"$set": updates}, upsert=True)
            await m.reply_text(f"✅ Updated menu for **{MODELS[model_key]['name']}**.", quote=True)

        except Exception as e:
            await _reply_err(m, e, "editmenu")

    # /deletemenu <Model>
    @app.on_message(filters.command("deletemenu"))
    async def deletemenu(_: Client, m: Message):
        try:
            if not m.from_user: return
            args = _split_args(m)
            if len(args) < 2:
                await m.reply_text("Usage:\n`/deletemenu <ModelName>`", quote=True); return

            model_key = _model_key_from_name(args[1])
            if not model_key:
                await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return
            if not _can_edit_model(m.from_user.id, getattr(m.from_user, "username", None), model_key):
                await m.reply_text("⛔ You aren’t allowed to delete that model’s menu.", quote=True); return

            res = col_model_menus.delete_one({"key": model_key})
            if res.deleted_count:
                await m.reply_text(f"🗑️ Deleted menu for **{MODELS[model_key]['name']}**.", quote=True)
            else:
                await m.reply_text("There was no stored menu for that model.", quote=True)

        except Exception as e:
            await _reply_err(m, e, "deletemenu")

    # /viewmenu <Model>  (quick preview of saved menu)
    @app.on_message(filters.command("viewmenu"))
    async def viewmenu(_: Client, m: Message):
        try:
            args = _split_args(m)
            if len(args) < 2:
                await m.reply_text("Usage:\n`/viewmenu <ModelName>`", quote=True); return

            model_key = _model_key_from_name(args[1])
            if not model_key:
                await m.reply_text("Unknown model. Use **Roni**, **Ruby**, **Rin**, or **Savy**.", quote=True); return

            doc = col_model_menus.find_one({"key": model_key})
            if not doc:
                await m.reply_text("⚠️ No menu saved yet.", quote=True); return

            text = (doc.get("text") or "").strip() or f"{MODELS[model_key]['name']}'s menu"
            photo_id = doc.get("photo_id")
            if photo_id:
                await m.reply_photo(photo=photo_id, caption=text)
            else:
                await m.reply_text(text)

        except Exception as e:
            await _reply_err(m, e, "viewmenu")
