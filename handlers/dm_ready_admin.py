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
BOT_ID = int(os.getenv("BOT_ID", "0") or "0")  # Optional: set to bot's ID to always hide it

def _allowed(uid: int) -> bool:
    return uid == OWNER_ID

def _fmt_la(ts_iso: str | None) -> str:
    if not ts_iso:
        return "-"
    try:
        dt = dtparse.parse(ts_iso)
        if dt.tzinfo is None:
            # treat naive as already LA (conservative)
            dt = LA_TZ.localize(dt)
        else:
            dt = dt.astimezone(LA_TZ)
        return dt.strftime("%Y-%m-%d %I:%M %p PT")
    except Exception:
        return str(ts_iso or "-")

def register(app: Client):
    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def dmready_list(c: Client, m: Message):
        if not m.from_user or not _allowed(m.from_user.id):
            return

        me = await c.get_me()
        me_id = me.id if me else 0

        rows = []
        for r in store.all():
            # Only show users with a first-mark timestamp and hide bot/self if present
            if not r.first_marked_iso:
                continue
            if r.user_id in {me_id, BOT_ID}:
                continue
            rows.append(r)

        rows.sort(key=lambda x: x.first_marked_iso or "")

        if not rows:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        out = ["✅ *DM-ready users*"]
        for i, r in enumerate(rows, 1):
            at = f"@{r.username}" if r.username else ""
            out.append(f"{i}. {at} — `{r.user_id}` — {_fmt_la(r.first_marked_iso)}")

        await m.reply_text("\n".join(out), disable_web_page_preview=True)
