# handlers/dm_ready_admin.py
# /dmreadylist (aliases: /dmreadys, /dmready_list) — show persisted DM-ready users.

from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import DMReadyStore

store = DMReadyStore()

def _is_allowed(user_id: int) -> bool:
    # Prefer your project’s checker if it exists
    try:
        from utils.admin_check import is_admin_or_owner  # type: ignore
        return bool(is_admin_or_owner(user_id))
    except Exception:
        pass

    # Fallback to OWNER_ID / SUPER_ADMINS envs
    owner = (os.getenv("OWNER_ID") or "").strip()
    supers = [s.strip() for s in (os.getenv("SUPER_ADMINS") or "").split(",") if s.strip()]
    return str(user_id) == owner or str(user_id) in supers

def register(app: Client):

    @app.on_message(filters.command(["dmreadylist", "dmreadys", "dmready_list"]))
    async def dmready_list(client: Client, m: Message):
        if not _is_allowed(m.from_user.id):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        users = store.list_all()  # newest first
        if not users:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

        # Keep output tidy (first 200 entries)
        lines = []
        for i, u in enumerate(users[:200], start=1):
            name = u.get("first_name") or "User"
            uname = ("@" + u["username"]) if u.get("username") else ""
            uid = u.get("id")
            lines.append(f"{i}. {name} {uname} — <code>{uid}</code>")
        text = "✅ <b>DM-ready users</b>\n" + "\n".join(lines)
        await m.reply_text(text, disable_web_page_preview=True)
