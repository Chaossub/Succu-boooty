# handlers/dmnow.py
from __future__ import annotations
import logging

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

log = logging.getLogger("dmnow")

# ---- Optional ReqStore integration (marks DM-ready) -------------------------
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None


def _set_dm_ready(uid: int) -> bool:
    """
    Best-effort: mark user as DM-ready.
    Returns True if we changed it from False->True, False if it was already True or failed.
    """
    if not _store or not uid:
        return False
    try:
        # Prefer global API if present
        if hasattr(_store, "is_dm_ready_global") and hasattr(_store, "set_dm_ready_global"):
            if not _store.is_dm_ready_global(uid):
                _store.set_dm_ready_global(uid, True, by_admin=False)
                return True
            return False
        # Fallback older API
        if hasattr(_store, "is_dm_ready") and hasattr(_store, "set_dm_ready"):
            if not _store.is_dm_ready(uid):
                _store.set_dm_ready(uid, True)
                return True
            return False
    except Exception as e:
        log.warning(f"Failed to set dm-ready for {uid}: {e}")
    return False


def _open_dm_kb(bot_username: str) -> InlineKeyboardMarkup:
    # Deep-link to open bot DM and land on our portal
    url = f"https://t.me/{bot_username}?start=portal"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💬 Open DM with SuccuBot", url=url)]]
    )


def register(app: Client):

    @app.on_message(filters.command(["dmnow"]))
    async def dmnow(client: Client, m: Message):
        """
        /dmnow — Give the user a button to open the bot DM, and mark them DM-ready.
        Safe in groups or DMs. No duplicate messages; DM-ready is set now so the
        /start portal won't announce it again.
        """
        if not m.from_user:
            return

        uid = m.from_user.id

        # Mark DM-ready *first*, so when they /start in DM we won't re-announce
        changed = _set_dm_ready(uid)
        # Get bot username (prefer cached; fetch if needed)
        try:
            me = await client.get_me()
            bot_username = me.username or ""
        except Exception:
            bot_username = ""

        if not bot_username:
            # Fallback text if bot username is somehow missing
            return await m.reply_text(
                "I couldn't determine my @username to build the DM link. "
                "Please set the bot username in BotFather."
            )

        # Build keyboard and reply
        kb = _open_dm_kb(bot_username)
        msg = "Tap below to open a private chat with me.\n\n" \
              "Once you open the DM, press <b>Start</b> to enter the portal."
        if changed:
            # Quietly note we marked them; keeps behavior clear during testing
            msg += "\n\n✅ You’re marked DM-ready."

        await m.reply_text(msg, reply_markup=kb, disable_web_page_preview=True)
