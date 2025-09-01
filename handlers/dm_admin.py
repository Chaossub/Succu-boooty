# handlers/dm_admin.py
# /dmreadylist for admins/owner — lists all currently DM-ready users (persisted)
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import DMReadyStore

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {int(x) for x in (os.getenv("SUPER_ADMINS","").replace(" ","").split(",") if os.getenv("SUPER_ADMINS") else []) if x}

store = DMReadyStore()

def _is_adminish(uid: int) -> bool:
    return uid == OWNER_ID or (uid in SUPER_ADMINS)

def register(app: Client):

    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list(client: Client, m: Message):
        if not _is_adminish(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        rows = store.all()
        if not rows:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")
        lines = ["✅ <b>DM-ready users</b>"]
        for i, row in enumerate(rows, start=1):
            handle = f"@{row.get('username')}" if row.get("username") else ""
            lines.append(f"{i}. {row.get('first_name','User')} {handle} — {row['user_id']}")
        await m.reply_text("\n".join(lines))
