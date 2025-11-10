# handlers/menu.py
# Lists and shows menus from the same persistent store as /createmenu
import logging
from pyrogram import filters
from utils.menu_store import store  # <- SAME store

log = logging.getLogger(__name__)

def register(app):
    log.info("✅ handlers.menu registered (storage=%s)",
             "Mongo" if store.uses_mongo() else "JSON")

    @app.on_message(filters.command("menu"))
    async def list_menus(_, m):
        names = store.list_names()  # alias to all_models()
        if not names:
            return await m.reply("No menus yet. Create one with /createmenu <Name> <text...>")
        items = "\n".join(f"• {n}" for n in names)
        await m.reply(f"<b>Available Menus</b>\n{items}\n\nUse <code>/showmenu &lt;Name&gt;</code>")

    @app.on_message(filters.command("showmenu"))
    async def show_menu(_, m):
        tokens = (m.text or "").split(maxsplit=1)
        if len(tokens) < 2:
            return await m.reply("Usage: /showmenu <Name>")
        name = tokens[1].strip()
        text = store.get_menu(name)
        if text is None:
            return await m.reply(f"Menu '<b>{name}</b>' not found.")
        await m.reply(text)
