# handlers/dm_admin.py
# Admin DM helper:
#   /dmnow – post a deep-link that opens a DM with this bot.
# NOTE: DM-ready listing lives in handlers/dm_ready_admin.py.

from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message

def _is_allowed(uid: int) -> bool:
    # Prefer your project helper if present
    try:
        from utils.admin_check import is_admin_or_owner  # type: ignore
        return bool(is_admin_or_owner(uid))
    except Exception:
        pass
    owner = (os.getenv("OWNER_ID") or "").strip()
    supers = [s.strip() for s in (os.getenv("SUPER_ADMINS") or "").split(",") if s.strip()]
    return str(uid) == owner or str(uid) in supers

def _bot_link(username: str) -> str:
    return f"https://t.me/{username}?start=ready"

def register(app: Client):

    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        """
        Usage:
          • reply to a user's message with /dmnow
          • or /dmnow @username
          • or /dmnow <user_id>
        """
        uid = m.from_user.id if m.from_user else 0
        if not _is_allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        me = await client.get_me()
        url = _bot_link(me.username)

        target_text = None
        if m.reply_to_message and m.reply_to_message.from_user:
            u = m.reply_to_message.from_user
            at = ("@" + u.username) if u.username else f"<code>{u.id}</code>"
            target_text = f"{u.first_name} {at}"
        elif m.text and len(m.text.split()) > 1:
            target_text = m.text.split(maxsplit=1)[1].strip()

        if target_text:
            msg = f"💌 Tap to open a DM with the bot for {target_text}:\n{url}"
        else:
            msg = f"💌 Tap to open a DM with the bot:\n{url}"

        # DM-ready is marked after they press Start in DM (handled in dm_foolproof.py)
        await m.reply_text(msg, disable_web_page_preview=True)
