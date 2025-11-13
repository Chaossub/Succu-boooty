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
    """Only owner + SUPER_ADMINS can use /createmenu."""
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def register(app: Client) -> None:
    log.info("✅ handlers.createmenu registered (Mongo=%s)", store.uses_mongo())

    # DM-only, command-only handler
    @app.on_message(filters.private & filters.command("createmenu"))
    async def createmenu_cmd(_, m: Message):
        try:
            if not m.from_user:
                return

            uid = m.from_user.id

            # Permission check
            if not _allowed(uid):
                await m.reply_text(
                    "❌ This command is reserved for Roni and approved admins only."
                )
                return

            text = (m.text or "").strip()

            # Strip the /createmenu part
            parts = text.split(" ", 1)
            if len(parts) < 2:
                await m.reply_text(USAGE)
                return

            rest = parts[1].strip()

            # Expect: ModelName | Menu body...
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

            # Save to Mongo
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
