# /createmenu <Name> <text...>  -> saves to persistent store
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.menu_store import store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {int(x) for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split() if x.isdigit()}

REGISTERED = False  # guard against double import

def _allowed(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS

def register(app: Client):
    global REGISTERED
    if REGISTERED:
        return
    REGISTERED = True

    @app.on_message(filters.command("createmenu"))
    async def createmenu(_, m: Message):
        if not (m.from_user and _allowed(m.from_user.id)):
            return await m.reply_text("❌ you can’t use this command.")

        # supports:
        #   /createmenu Name text...
        #   reply to a message with /createmenu Name  (uses the replied text)
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) == 2 and m.reply_to_message:
            name = parts[1].strip()
            text = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()
        elif len(parts) >= 3:
            name, text = parts[1].strip(), parts[2].strip()
        else:
            return await m.reply_text(
                "usage:\n"
                "• /createmenu Name text…\n"
                "• or reply to a message with: /createmenu Name"
            )

        if not name or not text:
            return await m.reply_text("please give me a Name and some text 💖")

        store.set_menu(name, text)
        await m.reply_text(
            f"✅ saved menu for {name}.\nopen with /showmenu {name} or tap it in /menus"
        )
