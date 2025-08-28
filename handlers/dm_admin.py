# handlers/dm_admin.py
from typing import List
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import DMReadyStore
from utils.admin_check import require_admin

_store = DMReadyStore()

def _fmt_list(rows: List[dict]) -> str:
    if not rows:
        return "ℹ️ No one is marked DM-ready yet."
    lines = ["✅ <b>DM-ready users</b>"]
    for i, d in enumerate(rows, 1):
        handle = f"@{d.get('username')}" if d.get("username") else ""
        lines.append(f"{i}. {d.get('first_name') or 'User'} {handle} — <code>{d.get('user_id')}</code>")
    return "\n".join(lines)

def register(app: Client):

    @app.on_message(filters.private & filters.command("dmreadylist"))
    @require_admin
    async def dmready_list(client: Client, m: Message):
        docs = _store.get_all_dm_ready_global()
        await m.reply_text(_fmt_list(docs))

    @app.on_message(filters.private & filters.command("dmreadyclear"))
    @require_admin
    async def dmready_clear(client: Client, m: Message):
        _store.clear_dm_ready_global()
        await m.reply_text("🧹 Cleared all DM-ready flags.")

    @app.on_message(filters.private & filters.command("dmreadyremove"))
    @require_admin
    async def dmready_remove(client: Client, m: Message):
        # usage: /dmreadyremove <user_id>
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            await m.reply_text("Usage: <code>/dmreadyremove 123456789</code>")
            return
        try:
            uid = int(parts[1].strip())
        except Exception:
            await m.reply_text("Invalid user id.")
            return
        ok = _store.remove_dm_ready_global(uid)
        await m.reply_text("✅ Removed." if ok else "ℹ️ Not found.")
