# handlers/createmenu.py
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


def _allowed(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def register(app: Client):
    log.info("✅ handlers.createmenu ready (Mongo=%s)", store.uses_mongo())

    @app.on_message(filters.command("createmenu"))
    async def createmenu_cmd(_, m: Message):
        try:
            if not m.from_user:
                return

            uid = m.from_user.id
            log.info("/createmenu from %s", uid)

            # Permission check
            if not _allowed(uid):
                await m.reply_text("❌ You’re not allowed to use this command.")
                return

            text = m.text or ""
            parts = text.split(maxsplit=2)

            # We expect: /createmenu <Name> <menu text...>
            if len(parts) < 3:
                await m.reply_text(
                    "Usage:\n"
                    "<code>/createmenu &lt;Name&gt; &lt;text...&gt;</code>\n\n"
                    "Example:\n"
                    "<code>/createmenu Rin My cute menu text…</code>",
                    disable_web_page_preview=True,
                )
                return

            name = parts[1].strip()
            body = parts[2].strip()

            if not name:
                await m.reply_text("❌ Menu name cannot be empty.")
                return
            if not body:
                await m.reply_text("❌ Menu text cannot be empty.")
                return

            # Save to store (Mongo or JSON behind the scenes)
            store.set_menu(name, body)
            log.info("Saved menu for %r (len=%d)", name, len(body))

            await m.reply_text(
                f"✅ Saved menu for <b>{name}</b>.\n"
                f"(Length: {len(body)} characters)\n\n"
                f"Use <code>/showmenu {name}</code> or tap their name in the Menus panel.",
                disable_web_page_preview=True,
            )

        except Exception as e:
            log.exception("/createmenu crashed: %s", e)
            await m.reply_text(f"❌ Failed to save menu: <code>{e}</code>")

