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
    "✨ <b>Create a model menu</b>\n\n"
    "<code>/createmenu Model Name\n"
    "Full menu text here\n"
    "More lines…</code>\n\n"
    "First line after the command = model name\n"
    "Everything after = menu text"
)


def _allowed(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def register(app: Client) -> None:
    log.info("✅ handlers.createmenu registered (Mongo=%s)", store.uses_mongo())

    @app.on_message(filters.private & filters.text, group=-1)
    async def createmenu_cmd(_, m: Message):
        try:
            if not m.from_user or not m.text:
                return

            text = m.text.strip()

            # Only process if message begins with /createmenu
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
                await m.reply_text("❌ This command is for Roni and approved admins only.")
                return

            # Split lines
            lines = text.splitlines()

            # Must have at least command + name + menu lines
            if len(lines) < 2:
                await m.reply_text(USAGE)
                return

            # First line after command = model name
            first_line = lines[0].split(" ", 1)
            if len(first_line) < 2:
                await m.reply_text(USAGE)
                return

            model_name = first_line[1].strip()
            menu_body = "\n".join(lines[1:]).strip()

            if not model_name or not menu_body:
                await m.reply_text(USAGE)
                return

            # Save in Mongo/JSON
            store.set_menu(model_name, menu_body)
            log.info("💾 Saved menu for model=%r", model_name)

            await m.reply_text(
                f"✅ Saved menu for <b>{model_name}</b>.\n\n"
                "You can now attach it to any button in the Menus panel.",
                disable_web_page_preview=True,
            )

        except Exception as e:
            log.exception("createmenu failed: %s", e)
            await m.reply_text(
                "❌ Something went wrong while saving the menu:\n"
                f"<code>{e}</code>"
            )
