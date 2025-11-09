# handlers/dm_ready.py
from __future__ import annotations
import os
from datetime import datetime, timezone
import pytz
from dateutil import parser as dtparse
from typing import Set

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.dmready_store import global_store as store

LA_TZ = pytz.timezone("America/Los_Angeles")
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DEBUG_DMREADY_CONFIRM = (os.getenv("DEBUG_DMREADY_CONFIRM", "0") == "1")

_seen_msgs: Set[int] = set()  # in-process dedupe in case handlers get registered twice

def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

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

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data="menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )

WELCOME = (
    "🔥 *Welcome to SuccuBot* 🔥\n"
    "I'm your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(_: Client, m: Message):
        # simple guard against double-processing the same message id
        if m.id in _seen_msgs:
            return
        _seen_msgs.add(m.id)

        u = m.from_user
        if not u:
            return

        rec = store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
            when_iso=_now_iso_utc(),
        )

        if DEBUG_DMREADY_CONFIRM:
            await m.reply_text(
                f"✅ DM-ready: {u.first_name} @{u.username or ''} — {u.id}\n{_fmt_la(rec.first_marked_iso)}"
            )

        await m.reply_text(WELCOME, reply_markup=_home_kb(), disable_web_page_preview=True)

    @app.on_message(filters.private & filters.command("dmready"))
    async def dmready(_: Client, m: Message):
        u = m.from_user
        if not u:
            return
        rec = store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
            when_iso=_now_iso_utc(),
        )
        await m.reply_text(
            f"✅ DM-ready: {u.first_name} @{u.username or ''}\n{_fmt_la(rec.first_marked_iso)}"
        )
