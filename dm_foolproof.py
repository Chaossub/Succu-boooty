# handlers/dm_foolproof.py
# Handles /start deep-link and marks DM-ready (once, persisted).
import os
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DMREADY_ECHO_IN_DM = os.getenv("DMREADY_ECHO_IN_DM", "0") == "1"

# Optional: announce to a sanctuary log chat (not the public group)
SANCTUARY_LOG_CHAT_ID = int(os.getenv("SANCTUARY_CHAT_ID", "0") or "0")


def _dm_portal_keyboard(bot_username: Optional[str]) -> InlineKeyboardMarkup:
    rows = []
    if bot_username:
        rows.append([InlineKeyboardButton("💌 Open Portal", url=f"https://t.me/{bot_username}?start=ready")])
    return InlineKeyboardMarkup(rows) if rows else None  # type: ignore[return-value]


def register(app: Client) -> None:
    store = DMReadyStore()

    @app.on_message(filters.private & filters.command("start"))
    async def start_mark_ready(client: Client, m: Message):
        # Mark user DM-ready if new
        user = m.from_user
        if not user:
            return

        is_new, doc = store.set_ready(
            user_id=user.id,
            username=(user.username or None),
            first_name=(user.first_name or None),
        )

        # Optionally echo in the DM (off by default to avoid "duplicates")
        if DMREADY_ECHO_IN_DM and is_new:
            try:
                await m.reply_text(
                    f"✅ <b>DM-ready</b> — {user.first_name or 'User'}"
                    + (f" @{user.username}" if user.username else ""),
                    quote=False,
                )
            except Exception:
                pass

        # Notify OWNER_ID once, when new
        if is_new and OWNER_ID:
            try:
                uname = f"@{user.username}" if user.username else "(no username)"
                await client.send_message(
                    OWNER_ID,
                    f"✅ <b>DM-ready</b> — {user.first_name or 'User'} {uname} — <code>{user.id}</code>",
                )
            except Exception as e:
                log.warning("Failed DM-ready owner notify: %s", e)

        # Optional sanctuary log chat
        if is_new and SANCTUARY_LOG_CHAT_ID:
            try:
                uname = f"@{user.username}" if user.username else "(no username)"
                await client.send_message(
                    SANCTUARY_LOG_CHAT_ID,
                    f"✅ DM-ready — {user.first_name or 'User'} {uname}",
                )
            except Exception as e:
                log.warning("Group announce failed for %s: %s", SANCTUARY_LOG_CHAT_ID, e)

        # If you want to always present a portal button here, uncomment:
        # me = await client.get_me()
        # kb = _dm_portal_keyboard(me.username)
        # if kb:
        #     with contextlib.suppress(Exception):
        #         await m.reply_text("Tap to reopen your portal anytime:", reply_markup=kb, quote=False)
