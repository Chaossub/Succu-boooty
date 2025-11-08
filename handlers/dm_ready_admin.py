# handlers/dmready_admin.py
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

def _fmt_la(ts: str | None) -> str:
    """Coerce any reasonably parseable timestamp (UTC or local) to LA time."""
    if not ts:
        return "—"
    try:
        dt = dtparse.parse(ts)
        # If naïve, assume it's already LA; otherwise convert
        if dt.tzinfo is None:
            dt = LA_TZ.localize(dt)
        else:
            dt = dt.astimezone(LA_TZ)
        return dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")
    except Exception:
        return ts  # show raw if parsing fails

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
            first_seen = _fmt_la(r.get("first_seen"))
            lines.append(
                f"{i}. {r.get('first_name','User')} {handle} — <code>{r['user_id']}</code> • {first_seen}"
            )
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
