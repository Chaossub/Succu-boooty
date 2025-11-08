# handlers/dmready_admin.py
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID

def register(app: Client):
    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list(_: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You can’t use this command.")

        rows = store.all()
        if not rows:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

        lines = ["✅ <b>DM-ready users</b>"]
        for i, r in enumerate(rows, start=1):
            handle = f"@{r.get('username')}" if r.get("username") else ""
            first_seen = r.get("first_seen", "—")
            lines.append(f"{i}. {r.get('first_name','User')} {handle} — <code>{r['user_id']}</code> • {first_seen}")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
