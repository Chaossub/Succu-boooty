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
    "<code>/createmenu Roni\n"
    "GFE Chat: $25 / day\n"
    "Sexting: $30 / day\n"
    "Customs: $15+\n"
    "</code>\n\n"
    "Line 1 = model name\n"
    "Everything after = menu text."
)


def _allowed(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS


def clean_name(name: str) -> str:
    """Remove bars, trailing spaces, emojis, and normalize spacing."""
    if not name:
        return ""
    cleaned = (
        name.replace("|", "")
            .replace(":", "")
            .strip()
    )
    # collapse duplicate spaces
    cleaned = " ".join(cleaned.split())
    return cleaned


def register(app: Client) -> None:
    log.info("✅ handlers.createmenu registered (Mongo=%s)", store.uses_mongo())

    @app.on_message(filters.private & filters.text, group=-1)
    async def createmenu_cmd(_, m: Message):
        try:
            if not m.from_user or not m.text:
                return

            txt = m.text.strip()

            if not txt.lower().startswith("/createmenu"):
                return

            uid = m.from_user.id
            log.info("📥 /createmenu from %s: %r", uid, txt)

            if not _allowed(uid):
                await m.reply_text("❌ Only Roni or approved admins can create menus.")
                return

            # Remove command
            after = txt.split("\n")
            if len(after) < 2:
                await m.reply_text(USAGE)
                return

            # Line 1 after command = name
            first_line = after[0].replace("/createmenu", "").strip()

            name = clean_name(first_line)

            if not name:
                await m.reply_text("❌ I couldn't detect a valid model name.\n\n" + USAGE)
                return

            # Everything after line 1 is body
            body_lines = after[1:]
            body = "\n".join(body_lines).strip()

            if not body:
                await m.reply_text("❌ Menu text cannot be empty.\n\n" + USAGE)
                return

            # Save it
            store.set_menu(name, body)

            await m.reply_text(
                f"✅ Saved menu for <b>{name}</b>.\n"
                "You can now attach it to buttons in the Menus panel."
            )

        except Exception as e:
            log.exception("createmenu failed: %s", e)
            await m.reply_text(f"❌ Error:\n<code>{e}</code>")
