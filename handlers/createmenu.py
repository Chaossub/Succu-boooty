# handlers/createmenu.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {
    int(x)
    for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split()
    if x.isdigit()
}

USAGE = (
    "✨ <b>Create a menu</b>\n\n"
    "<code>/createmenu Savy PREMADE MENU\\n"
    "Videos\\n"
    "Solo $4/min\\n"
    "...</code>\n\n"
    "The first word after /createmenu is the model's key name "
    "(must match the button, e.g. Roni, Rin, Savy, Ruby).\n"
    "Everything after that becomes the full menu text."
)


def _allowed(user_id: int) -> bool:
    # Only Roni + SUPER_ADMINS
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def register(app: Client) -> None:
    log.info("✅ handlers.createmenu registered (Mongo=%s)", store.uses_mongo())

    # HIGH PRIORITY: group = -1 so this runs before generic DM handlers
    @app.on_message(filters.private & filters.text, group=-1)
    async def createmenu_cmd(_, m: Message):
        try:
            if not m.from_user or not m.text:
                return

            text = m.text.strip()

            # Only handle /createmenu messages
            if not text.lower().startswith("/createmenu"):
                return

            uid = m.from_user.id
            log.info(
                "📥 /createmenu from %s (%s): %r",
                uid,
                m.from_user.first_name,
                text,
            )

            if not _allowed(uid):
                await m.reply_text(
                    "❌ This command is reserved for Roni and approved admins only."
                )
                return

            # Split into: ['/createmenu', <name>, <full body…>]
            parts = text.split(None, 2)  # split on any whitespace, max 2 splits
            if len(parts) < 3:
                await m.reply_text(USAGE)
                return

            _, name, body = parts
            name = name.strip()
            body = body.strip()

            if not name or not body:
                await m.reply_text(
                    "❌ I need a model name and menu text.\n\n" + USAGE
                )
                return

            # Save menu in Mongo/JSON
            log.info("💾 Saving menu for model=%r", name)
            store.set_menu(name, body)

            await m.reply_text(
                f"✅ Saved menu for <b>{name}</b>.\n\n"
                "You can now attach it to buttons using the Menus panel.",
                disable_web_page_preview=True,
            )

        except Exception as e:
            log.exception("createmenu failed: %s", e)
            await m.reply_text(
                "❌ Something went wrong while saving that menu:\n"
                f"<code>{e}</code>"
            )
