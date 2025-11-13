# handlers/createmenu.py

import os
import logging
from pyrogram import Client
from pyrogram.types import Message
from utils.menu_store import store

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# PERMISSIONS
# ─────────────────────────────────────────────
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {
    int(x)
    for x in os.getenv("SUPER_ADMINS", "").replace(",", " ").split()
    if x.isdigit()
}


def _allowed(user_id: int) -> bool:
    """Only owner + SUPER_ADMINS can create/update menus."""
    if OWNER_ID and user_id == OWNER_ID:
        return True
    if user_id in SUPER_ADMINS:
        return True
    return False


USAGE = (
    "<b>Create or update a model menu</b>\n\n"
    "You can use either format:\n\n"
    "1️⃣ Reply mode:\n"
    "   • Send the full menu text.\n"
    "   • Reply to that message with:\n"
    "     <code>/createmenu ModelName</code>\n\n"
    "2️⃣ Inline mode (one message):\n"
    "   <code>/createmenu ModelName | menu text…</code>\n\n"
    "Example:\n"
    "<code>/createmenu Roni | Roni's Menu\n"
    "• GFE: $25/day\n"
    "• Sexting: $30/day\n"
    "• Customs: $15+</code>\n\n"
    "The menu will appear in /menus and in tip buttons."
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _strip_command_prefix(text: str) -> str:
    """
    Remove '/createmenu' or '/createmenu@BotName' from the start of the text
    and return the rest.
    """
    # Split into first word + the rest
    parts = text.split(maxsplit=1)
    cmd = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    # Handle '/createmenu' and '/createmenu@Something'
    if cmd.startswith("/createmenu"):
        return rest.strip()

    return text.strip()


def _parse_inline(text: str):
    """
    After stripping the command, parse: 'Name | body...'
    Returns (name, body) or (None, None).
    """
    if not text:
        return None, None

    if "|" not in text:
        # Name only
        return text.strip(), ""

    name, body = text.split("|", 1)
    name = name.strip()
    body = body.strip()

    if not name:
        return None, None

    return name, body


# ─────────────────────────────────────────────
# REGISTER HANDLER
# ─────────────────────────────────────────────
def register(app: Client):
    log.info("✅ handlers.createmenu registered")

    # CATCH **ALL** MESSAGES
    @app.on_message()
    async def createmenu_cmd(_, m: Message):
        text = (m.text or m.caption or "").strip()

        # DEBUG LOG FOR EVERY MESSAGE
        log.info("[createmenu] got message: %r from %s", text, m.from_user.id if m.from_user else None)

        # Only react if the word 'createmenu' appears anywhere
        if "createmenu" not in text.lower():
            return

        log.info("[createmenu] matched text, starting handler logic")

        # Permissions
        user_id = m.from_user.id if m.from_user else 0
        if not _allowed(user_id):
            await m.reply_text("❌ You are not allowed to create or edit menus.")
            return

        name = None
        body = None

        # ────────────── MODE 1: Reply mode ──────────────
        if m.reply_to_message:
            rest = _strip_command_prefix(text)
            if not rest:
                await m.reply_text(USAGE)
                return

            name = rest
            body = (
                m.reply_to_message.text
                or m.reply_to_message.caption
                or ""
            ).strip()

            if not body:
                await m.reply_text(
                    "❌ The replied message has no text to save as a menu.\n\n" + USAGE
                )
                return

        # ────────────── MODE 2: Inline / single message ──────────────
        else:
            rest = _strip_command_prefix(text)
            name, body = _parse_inline(rest)

            if not name:
                await m.reply_text(USAGE)
                return

            if not body:
                await m.reply_text(
                    "❌ No menu text detected after the model name.\n\n" + USAGE
                )
                return

        # ────────────── VALIDATION ──────────────
        if len(name) > 64:
            await m.reply_text("❌ Model name is too long (max 64 characters).")
            return

        # ────────────── SAVE TO MONGO ──────────────
        try:
            store.set_menu(name, body)
            log.info("[createmenu] stored menu for %s", name)
            await m.reply_text(
                f"✅ Saved menu for <b>{name}</b>.",
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.exception("❌ Error saving menu: %s", e)
            await m.reply_text(f"❌ Failed to save menu:\n<code>{e}</code>")
