# handlers/dm_admin.py
# /dmreadylist  /dmreadyremove <id>  /dmreadyclear

from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import DMReadyStore
from utils.admin_check import require_admin

_store = DMReadyStore()

def _fmt(rows):
    if not rows: return "ℹ️ No one is marked DM-ready yet."
    out = ["✅ <b>DM-ready users</b>"]
    for i, d in enumerate(sorted(rows, key=lambda x: x.get("ts", 0)), 1):
        handle = f"@{d.get('username')}" if d.get('username') else ""
        out.append(f"{i}. {d.get('first_name') or 'User'} {handle} — <code>{d.get('id')}</code>")
    return "\n".join(out)

def register(app: Client):

    @app.on_message(filters.private & filters.command("dmreadylist"))
    @require_admin
    async def dmready_list(client: Client, m: Message):
        await m.reply_text(_fmt(_store.list_all()))

    @app.on_message(filters.private & filters.command("dmreadyremove"))
    @require_admin
    async def dmready_remove(client: Client, m: Message):
        parts = m.text.split(maxsplit=1)
        if len(parts)<2:
            await m.reply_text("Usage: <code>/dmreadyremove 123456789</code>"); return
        try:
            uid = int(parts[1].strip())
        except Exception:
            await m.reply_text("Invalid user id."); return
        ok = _store.unset_dm_ready_global(uid)
        await m.reply_text("✅ Removed." if ok else "ℹ️ Not found.")

    @app.on_message(filters.private & filters.command("dmreadyclear"))
    @require_admin
    async def dmready_clear(client: Client, m: Message):
        for d in list(_store.list_all()):
            _store.unset_dm_ready_global(int(d["id"]))
        await m.reply_text("🧹 Cleared all DM-ready flags.")
