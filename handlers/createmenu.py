# handlers/createmenu.py
# /createmenu <model> <menu text>  (admins/owner/superadmins only)

import os
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.menu_store import MenuStore

try:
    from utils.admin_check import is_owner_or_admin_id
    def _allowed(client: Client, user_id: int) -> bool:
        return is_owner_or_admin_id(user_id)
except Exception:
    OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
    SUPER_ADMINS = {int(x) for x in os.getenv("SUPER_ADMINS","").replace(",", " ").split() if x.strip().isdigit()}
    def _allowed(client: Client, user_id: int) -> bool:
        return (user_id == OWNER_ID) or (user_id in SUPER_ADMINS)

MODEL_KEYS = ["roni", "ruby", "rin", "savy"]

def _env_name_to_key(name: str):
    name = (name or "").strip().lower()
    mapping = {}
    for k in MODEL_KEYS:
        env_name = os.getenv(f"{k.upper()}_NAME", "").strip().lower()
        if env_name:
            mapping[env_name] = k
    return mapping.get(name)

def _normalize_model(word: str):
    word = (word or "").strip().lower()
    if word in MODEL_KEYS:
        return word
    env_key = _env_name_to_key(word)
    return env_key

def register(app: Client):
    store = MenuStore()

    @app.on_message(filters.private & filters.command("createmenu"))
    async def create_menu(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _allowed(client, uid):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return

        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            await m.reply_text("Usage:\n<code>/createmenu roni &lt;menu text&gt;</code>")
            return

        model_word = parts[1]
        text = parts[2].strip()

        key = _normalize_model(model_word)
        if not key:
            await m.reply_text("Unknown model. Try one of: " + ", ".join(MODEL_KEYS))
            return

        store.set_menu(key, text)
        display = os.getenv(f"{key.upper()}_NAME", key.capitalize())
        await m.reply_text(f"✅ Saved menu for <b>{display}</b>.\nOpen <b>Menus</b> → {display} to see it.")
