# /createmenu <Name> <text...>  -> saves to persistent store
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

        # Accept either: /createmenu Name text...
        # ...or: reply to a message's text with "/createmenu Name"
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) == 2 and m.reply_to_message:
            name = parts[1].strip()
            text = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()
        elif len(parts) >= 3:
            name, text = parts[1].strip(), parts[2].strip()
        else:
            return await m.reply_text(
                "Usage:\n"
                "• <code>/createmenu &lt;Name&gt; &lt;text...&gt;</code>\n"
                "• or reply to a message: <code>/createmenu &lt;Name&gt;</code>",
                disable_web_page_preview=True,
            )

        if not name or not text:
            return await m.reply_text("Please provide both a <b>Name</b> and the <b>text</b>.")

        store.set_menu(name, text)
        await m.reply_text(
            f"✅ Saved menu for <b>{name}</b>.\nOpen <b>/showmenu {name}</b> or tap it in <b>/menus</b>.",
            disable_web_page_preview=True,
        )
