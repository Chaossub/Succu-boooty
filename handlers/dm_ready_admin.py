# handlers/dmready_admin.py — /dmreadylist with original timestamp
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
_SUPERS = {int(x) for x in (os.getenv("SUPER_ADMINS","").replace(" ","").split(",") if os.getenv("SUPER_ADMINS") else []) if x}

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID or uid in _SUPERS

def register(app: Client):
    @app.on_message(filters.command(["dmreadylist", "dmreadys", "dmready_list"]))
    async def dmready_list(_: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        rows = store.all()
        if not rows:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

        lines = ["✅ <b>DM-ready users</b>"]
        for i, r in enumerate(rows, start=1):
            handle = f"@{r.get('username')}" if r.get("username") else ""
            first_seen = r.get("first_seen", "—")
            lines.append(f"{i}. {r.get('first_name','User')} {handle} — <code>{r['user_id']}</code> • {first_seen}")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.command("dmreadyremove"))
    async def dmready_remove(_: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: <code>/dmreadyremove &lt;user_id&gt;</code>")
        try:
            target = int(parts[1].strip())
        except ValueError:
            return await m.reply_text("Please provide a numeric user_id.")
        ok = store.remove(target)
        await m.reply_text("✅ Removed." if ok else "ℹ️ That user wasn’t in the list.")
