# handlers/menu.py
import os, time
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# --- Mongo ---
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
mcli = MongoClient(MONGO_URL)
col = mcli[DB_NAME]["model_menus"]

# --- Auth ---
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMINS = [int(x) for x in os.getenv("SUPER_ADMINS", "").replace(" ", "").split(",") if x]

def is_admin(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS

# --- Models ---
MODELS = {
    "roni": os.getenv("RONI_NAME", "Roni"),
    "ruby": os.getenv("RUBY_NAME", "Ruby"),
    "rin":  os.getenv("RIN_NAME", "Rin"),
    "savy": os.getenv("SAVY_NAME", "Savy"),
}

def normalize_model(name: str):
    if not name: return None
    k = name.lower()
    if k in MODELS: return k
    for key, nm in MODELS.items():
        if nm.lower() == k: return key
    return None

# --- Register ---
def register(app: Client):

    @app.on_message(filters.command("createmenu"))
    async def createmenu(_: Client, m: Message):
        if not m.from_user:
            return

        parts = (m.caption or m.text or "").split(maxsplit=2)
        if len(parts) < 2:
            await m.reply("Usage: `/createmenu <Model> <text>` (optionally with photo)", quote=True)
            return

        model = normalize_model(parts[1])
        if not model:
            await m.reply("Unknown model. Use: Roni, Ruby, Rin, Savy.", quote=True)
            return

        if not is_admin(m.from_user.id):
            await m.reply("⛔ Only Owner/SUPER_ADMINS can set menus for now.", quote=True)
            return

        text = parts[2] if len(parts) >= 3 else ""
        photo_id = m.photo.file_id if m.photo else None

        col.update_one({"key": model}, {
            "$set": {
                "text": text,
                "photo_id": photo_id,
                "updated_at": int(time.time())
            }
        }, upsert=True)

        await m.reply(f"✅ Saved menu for **{MODELS[model]}**.", quote=True)

    @app.on_message(filters.command("viewmenu"))
    async def viewmenu(_: Client, m: Message):
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await m.reply("Usage: `/viewmenu <Model>`", quote=True); return

        model = normalize_model(parts[1])
        if not model:
            await m.reply("Unknown model.", quote=True); return

        doc = col.find_one({"key": model})
        if not doc:
            await m.reply("No menu saved.", quote=True); return

        if doc.get("photo_id"):
            await m.reply_photo(doc["photo_id"], caption=doc.get("text",""))
        else:
            await m.reply(doc.get("text","(empty)"))
