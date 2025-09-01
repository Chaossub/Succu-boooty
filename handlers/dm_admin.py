# handlers/dm_admin.py
# Admin tools: /dmreadylist, /dmreadyclear (reply or id), /dmreadywipe (owner only)
import os
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from utils.dmready_store import DMReadyStore
from utils.admin_check import is_admin_or_owner  # use your existing helper


OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")


def register(app: Client) -> None:
    store = DMReadyStore()

    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list(client: Client, m: Message):
        if not await is_admin_or_owner(client, m):
            return await m.reply_text("❌ You’re not allowed to use this command.", quote=True)

        docs = store.get_all()
        if not docs:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.", quote=True)

        lines = ["✅ <b>DM-ready users</b>"]
        for i, d in enumerate(docs, 1):
            uname = f"@{d.get('username')}" if d.get("username") else "(no username)"
            lines.append(f"{i}. {d.get('first_name','User')} {uname} — <code>{d.get('user_id')}</code>")
        await m.reply_text("\n".join(lines), quote=True)

    @app.on_message(filters.command("dmreadyclear"))
    async def dmready_clear(client: Client, m: Message):
        if not await is_admin_or_owner(client, m):
            return await m.reply_text("❌ You’re not allowed to use this command.", quote=True)

        target_id: Optional[int] = None
        if m.reply_to_message and m.reply_to_message.from_user:
            target_id = m.reply_to_message.from_user.id
        else:
            parts = (m.text or "").split(maxsplit=1)
            if len(parts) == 2 and parts[1].isdigit():
                target_id = int(parts[1])

        if not target_id:
            return await m.reply_text("Usage: <code>/dmreadyclear</code> (reply to a user) or <code>/dmreadyclear &lt;user_id&gt;</code>", quote=True)

        ok = store.clear(target_id)
        if ok:
            await m.reply_text(f"🧹 Cleared DM-ready for <code>{target_id}</code>.", quote=True)
        else:
            await m.reply_text("ℹ️ That user wasn’t marked DM-ready.", quote=True)

    @app.on_message(filters.command("dmreadywipe"))
    async def dmready_wipe(client: Client, m: Message):
        if not (m.from_user and m.from_user.id == OWNER_ID):
            return await m.reply_text("❌ Owner only.", quote=True)
        n = store.clear_all()
        await m.reply_text(f"🧨 Wiped DM-ready list ({n} removed).", quote=True)
