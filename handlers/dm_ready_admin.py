# handlers/dm_ready_admin.py
# Admin tools to view / manage DM-ready users (shared singleton store).
from __future__ import annotations
import os, logging
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

log = logging.getLogger(__name__)

def _allowed(uid: int) -> bool:
    """Use your existing utils.admin_check if available; otherwise fallback to env."""
    try:
        from utils.admin_check import is_admin_or_owner  # type: ignore
        return bool(is_admin_or_owner(uid))
    except Exception:
        owner = (os.getenv("OWNER_ID") or "").strip()
        supers = [s.strip() for s in (os.getenv("SUPER_ADMINS") or "").split(",") if s.strip()]
        allowed = set(filter(None, [owner, *supers]))
        return str(uid) in allowed

def register(app: Client):

    @app.on_message(filters.command(["dmreadylist", "dmreadys", "dmready_list"]))
    async def dmready_list(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        users = store.list_all()
        if not users:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")
        lines = []
        for i, u in enumerate(users[:400], start=1):
            uname = ("@" + u["username"]) if u.get("username") else ""
            lines.append(f"{i}. {u.get('first_name','User')} {uname} — <code>{u.get('id')}</code>")
        await m.reply_text("✅ <b>DM-ready users</b>\n" + "\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.command("dmreadyremove"))
    async def dmready_remove(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _allowed(uid):
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

    @app.on_message(filters.command("dmreadyclear"))
    async def dmready_clear(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        store.clear()
        await m.reply_text("🧹 Cleared DM-ready list.")

    @app.on_message(filters.command(["dmreadydebug", "dmready_dbg"]))
    async def dmready_debug(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _allowed(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        path = os.getenv("DMREADY_DB", "data/dm_ready.json")
        users = store.list_all()
        head = users[0] if users else {}
        await m.reply_text(
            "🧪 <b>DM-ready debug</b>\n"
            f"• File: <code>{path}</code>\n"
            f"• Count: <code>{len(users)}</code>\n"
            f"• First: <code>{head}</code>",
            disable_web_page_preview=True
        )

