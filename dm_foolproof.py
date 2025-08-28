# dm_foolproof.py
# Private /start portal + DM-ready tracker (persists via DMReadyStore)
from __future__ import annotations
import os, logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

WELCOME_TITLE = "🔥 <b>Welcome to SuccuBot</b> 🔥"
WELCOME_BODY  = (
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

BTN_MENUS   = os.getenv("BTN_MENU", "💕 Menus")
BTN_ADMINS  = "👑 Contact Admins"
BTN_FIND    = "🔥 Find Our Models Elsewhere"
BTN_HELP    = "❓ Help"

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_MENUS, callback_data="dmf_open_menu")],
        [InlineKeyboardButton(BTN_ADMINS, callback_data="dmf_contact_admins")],
        [InlineKeyboardButton(BTN_FIND, callback_data="dmf_find_models")],
        [InlineKeyboardButton(BTN_HELP, callback_data="dmf_help")],
    ])

_store = DMReadyStore()

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_portal(client: Client, m: Message):
        """Marks sender DM-ready (if first time), notifies OWNER once,
        and shows the main menu panel inside DM."""
        u = m.from_user
        if not u:
            return

        newly_added = _store.add(u.id, u.first_name, u.username)
        if newly_added:
            log.info(f"DM-ready NEW user {u.id} ({u.first_name})")
            # Notify only the owner (not groups)
            if OWNER_ID:
                uname = f"@{u.username}" if u.username else ""
                try:
                    await client.send_message(
                        OWNER_ID,
                        f"✅ DM-ready — {u.first_name} {uname}".strip()
                    )
                except Exception as e:
                    log.warning(f"Owner notify failed: {e}")

        # Show the DM portal
        await m.reply_text(
            f"{WELCOME_TITLE}\n{WELCOME_BODY}",
            reply_markup=kb_main(),
            disable_web_page_preview=True,
        )

    # The buttons referenced above are handled in your menu/contact/help handlers.
