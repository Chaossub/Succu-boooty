# /createmenu <Name> <text...>  -> saves to persistent store
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {
    int(x) for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split() if x.isdigit()
}

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS

def register(app: Client):
    log.info("✅ handlers.createmenu ready (Mongo=%s)", store.uses_mongo())

    @app.on_message(filters.command("createmenu"))
    async def createmenu(_: Client, m: Message):
        if not (m.from_user and _allowed(m.from_user.id)):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return

        raw = (m.text or "").strip()
        parts = raw.split(maxsplit=2)  # /createmenu <Name> <text...>
        if len(parts) < 3:
            await m.reply_text(
                "Usage:\n<code>/createmenu &lt;Name&gt; &lt;text...&gt;</code>",
                disable_web_page_preview=True,
            )
            return

        name = parts[1].strip()
        text = parts[2].strip()
        if not name or not text:
            await m.reply_text("❌ Provide a <b>Name</b> and <b>text</b>.")
            return

        try:
            store.set_menu(name, text)
            await m.reply_text(
                f"✅ Saved menu for <b>{name}</b>.\n"
                f"Open with <code>/showmenu {name}</code> or pick it in <code>/menus</code>.",
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.exception("createmenu failed: %s", e)
            await m.reply_text(f"❌ Failed to save: <code>{e}</code>")
