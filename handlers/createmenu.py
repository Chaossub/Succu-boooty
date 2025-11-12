# handlers/createmenu.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {int(x) for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split() if x.isdigit()}

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS

def register(app: Client):
    log.info("✅ handlers.createmenu ready (Mongo=%s)", store.uses_mongo())

    @app.on_message(filters.command("createmenu"))
    async def createmenu(_, m: Message):
        if not (m.from_user and _allowed(m.from_user.id)):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3:
            return await m.reply_text(
                "Usage:\n<code>/createmenu &lt;Name&gt; &lt;text...&gt;</code>",
                disable_web_page_preview=True,
            )

        name, text = parts[1].strip(), parts[2].strip()
        store.set_menu(name, text)
        await m.reply_text(
            f"✅ Saved menu for <b>{name}</b>.\nOpen <b>/showmenu {name}</b> or tap it in <b>/menus</b>.",
            disable_web_page_preview=True,
        )
