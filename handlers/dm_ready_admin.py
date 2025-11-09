# handlers/dm_ready_admin.py
from __future__ import annotations
import os
from datetime import datetime
import pytz
from dateutil import parser as dtparse
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

LA_TZ = pytz.timezone("America/Los_Angeles")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID

def _fmt_la(ts_iso: str | None) -> str:
    """Convert UTC or local ISO to readable Los Angeles time."""
    if not ts_iso:
        return "-"
    try:
        dt = dtparse.parse(ts_iso)
        if dt.tzinfo is None:
            dt = LA_TZ.localize(dt)
        else:
            dt = dt.astimezone(LA_TZ)
        return dt.strftime("%Y-%m-%d %I:%M %p PT")
    except Exception:
        return ts_iso

def register(app: Client):

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _dmreadylist(_: Client, m: Message):
        if not _allowed(m.from_user.id):
            await m.reply_text("❌ Owner only.")
            return

        users = sorted(store.all(), key=lambda r: r.first_marked_iso or "")
        if not users:
            await m.reply_text("✅ DM-ready users — none yet.")
            return

        lines = ["✅ DM-ready users"]
        for idx, u in enumerate(users, 1):
            uname = f"@{u.username}" if u.username else "-"
            when = _fmt_la(u.first_marked_iso)
            lines.append(f"{idx}. {uname} — `{u.user_id}` — {when}")
        await m.reply_text("\n".join(lines))

    @app.on_message(filters.private & filters.command("dmready"))
    async def _dmready(_: Client, m: Message):
        """Marks the current user as DM-ready (only first time persists)."""
        u = m.from_user
        rec = store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
        )
        when = _fmt_la(rec.first_marked_iso)
        await m.reply_text(f"✅ DM-ready: {u.first_name} @{u.username or ''}\n{when}")
