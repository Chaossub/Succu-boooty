# handlers/createmenu.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

def allowed(uid: int) -> bool:
    return uid == OWNER_ID

def register(app: Client):
    log.info("createmenu loaded")

    @app.on_message(filters.command("createmenu"))
    async def _cm(_, m: Message):
        if not allowed(m.from_user.id):
            return await m.reply("❌ Not allowed.")

        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            return await m.reply("Usage: /createmenu Name text...")

        name = parts[1]
        text = parts[2]

        store.set_menu(name, text)
        await m.reply(f"✅ Saved menu for {name}.")

