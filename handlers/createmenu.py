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
    "<code>/createmenu Roni | Roni's Main Menu\n"
    "• GFE Chat: $25 / day\n"
    "• Sexting: $30 / day\n"
    "• Customs: $15+\n"
    "…</code>\n\n"
    "First part = model name\n"
    "Text after <code>|</code> = full menu text."
)


def _allowed(user_id: int) -> bool:
    # Only Roni + SUPER_ADMINS
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def register(app: Client) -> None:
    log.info("✅ handlers.createmenu registered (Mongo=%s)", store.uses_mongo())

    # HIGH PRIORITY: group = -1 so this runs before any generic DM handlers
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

            # Remove the command part
            parts = text.split(" ", 1)
            if len(parts) < 2:
                await m.reply_text(USAGE)
                return

            rest = parts[1].strip()

            if "|" not in rest:
                await m.reply_text(
                    "❌ I couldn't see the <code>|</code> separator.\n\n" + USAGE
                )
                return

            name_part, body = rest.split("|", 1)
            name = name_part.strip()
            body = body.strip()

            if not name or not body:
                await m.reply_text(
                    "❌ I need both a model name and menu text.\n\n" + USAGE
                )
                return

            # Save menu in Mongo
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
