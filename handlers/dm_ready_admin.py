# handlers/dm_ready_admin.py
from __future__ import annotations
import os
from datetime import datetime
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
LA_TZ = pytz.timezone("America/Los_Angeles")

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID or str(uid) in {
        s.strip() for s in (os.getenv("SUPER_ADMINS","") or "").split(",") if s.strip()
    }

def _fmt_la(iso_utc: str | None) -> str:
    if not iso_utc:
        return "-"
    try:
        dt = datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=pytz.UTC).astimezone(LA_TZ)
        # e.g. 2025-11-07 08:15 PM PT
        return dt.strftime("%Y-%m-%d %I:%M %p PT")
    except Exception:
        return iso_utc

def register(app: Client):

    @app.on_message(filters.command(["dmreadylist", "dmreadys"]))
    async def dmready_list(client: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        users = sorted(store.all(), key=lambda r: r.get("first_marked_iso") or "")
        if not users:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")
        lines = ["✅ <b>DM-ready users</b>"]
        for i, u in enumerate(users, start=1):
            handle = f"@{u['username']}" if u.get("username") else ""
            when = _fmt_la(u.get("first_marked_iso"))
            lines.append(f"{i}. {u.get('first_name','User')} {handle} — <code>{u['id']}</code> • {when}")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.command("dmreadyremove"))
    async def dmready_remove(client: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: <code>/dmreadyremove &lt;user_id&gt;</code>")
        try:
            uid = int(parts[1].strip())
        except ValueError:
            return await m.reply_text("Please provide a numeric user_id.")
        ok = store.remove(uid)
        await m.reply_text("✅ Removed." if ok else "ℹ️ That user wasn’t in the list.")

    @app.on_message(filters.command("dmreadyclear"))
    async def dmready_clear(client: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        store.clear()
        await m.reply_text("🧹 Cleared DM-ready list.")

    @app.on_message(filters.command("dmreadydebug"))
    async def dmready_debug(client: Client, m: Message):
        if not _allowed(m.from_user.id if m.from_user else 0):
            return await m.reply_text("❌ You’re not allowed to use this command.")
        path = os.getenv("DMREADY_DB", "data/dm_ready.json")
        await m.reply_text(f"🧪 <b>DM-ready debug</b>\n• File: <code>{path}</code>\n• Count: <code>{len(store.all())}</code>")
