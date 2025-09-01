# /createmenu <model> <text...>  -> saves to persistent store
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.menu_store import store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {int(x) for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split() if x.isdigit()}

def _allowed(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS

def register(app: Client):
    @app.on_message(filters.command("createmenu"))
    async def createmenu(_, m: Message):
        if not (m.from_user and _allowed(m.from_user.id)):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            return await m.reply_text(
                "Usage: <code>/createmenu &lt;model&gt; &lt;text...&gt;</code>",
                disable_web_page_preview=True,
            )
        model, text = parts[1].strip(), parts[2].strip()
        store.set_menu(model, text)
        await m.reply_text(
            f"✅ Saved menu for <b>{model}</b>.\nOpen <b>Menus → {model}</b> to see it.",
            disable_web_page_preview=True,
        )
