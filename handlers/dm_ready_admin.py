# handlers/dm_ready_admin.py
from __future__ import annotations
import os
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
        return str(ts_iso or "-")

def register(app: Client):

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def dmready_list(_: Client, m: Message):
        if not m.from_user or not _allowed(m.from_user.id):
            return

        users = sorted(store.all(), key=lambda r: r.first_marked_iso or "")
        if not users:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        lines = ["✅ *DM-ready users*"]
        for i, rec in enumerate(users, 1):
            at = f"@{rec.username}" if rec.username else ""
            lines.append(f"{i}. {at} — `{rec.user_id}` — { _fmt_la(rec.first_marked_iso) }")

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
