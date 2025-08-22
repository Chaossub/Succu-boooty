# handlers/dm_admin.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

OWNER_ID        = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID  = int(os.getenv("SUPER_ADMIN_ID", "0")) or None
ADMIN_IDS = {i for i in (OWNER_ID, SUPER_ADMIN_ID) if i}

def _is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def register(app: Client):

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def dmready_list(client: Client, m: Message):
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 Admin only.")
        if not _store:
            return await m.reply_text("❌ DM-ready storage is not configured.")

        docs = _store.get_all_dm_ready_global()
        if not docs:
            return await m.reply_text("📋 Nobody is DM-ready yet.")

        lines = []
        for d in docs:
            uid = d.get("user_id")
            lines.append(f"✅ <a href='tg://user?id={uid}'>User {uid}</a>")
        await m.reply_text("📋 <b>DM-ready users</b>:\n\n" + "\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.private & filters.command("dmreadyclear"))
    async def dmready_clear(client: Client, m: Message):
        """ /dmreadyclear        → clear all
            /dmreadyclear <id>   → clear one
            (or reply to user’s message in DM and use /dmreadyclear)
        """
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 Admin only.")
        if not _store:
            return await m.reply_text("❌ DM-ready storage is not configured.")

        args = (m.text or "").split()
        target = None
        if len(args) >= 2 and args[1].isdigit():
            target = int(args[1])
        elif m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id

        if target is None:
            count = _store.clear_dm_ready_global(None)
            return await m.reply_text(f"🧹 Cleared DM-ready for <b>{count}</b> users.")
        else:
            count = _store.clear_dm_ready_global(target)
            return await m.reply_text("🧹 Cleared." if count else "Nothing to clear.")
