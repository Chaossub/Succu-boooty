# handlers/dm_ready.py
from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any

import pytz
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
LA_TZ = pytz.timezone("America/Los_Angeles")


def _now_iso_utc() -> str:
    # Always a Z-suffixed ISO string
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_any_iso_to_la(iso_str: str) -> str:
    if not iso_str:
        return "-"
    try:
        s = iso_str.replace("Z", "+00:00") if iso_str.endswith("Z") else iso_str
        dt_utc = datetime.fromisoformat(s)
        dt_la = dt_utc.astimezone(LA_TZ)
        return dt_la.strftime("%Y-%m-%d %I:%M %p PT").lstrip("0")
    except Exception:
        return iso_str


def _get(rec: Any, key: str, default=None):
    # Works with dicts, objects, or namedtuples/dataclasses
    if isinstance(rec, dict):
        return rec.get(key, default)
    return getattr(rec, key, default)


def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _on_start_mark(_: Client, m: Message):
        """
        Only *mark* the user as DM-ready ONCE, never reply here.
        The visible welcome is handled in handlers/start.py.
        """
        u = m.from_user
        if not u:
            return

        # Robust call: some store versions return the first ISO string,
        # others return a record. We don't need the return value here.
        store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
            first_name=u.first_name or "",
            last_name=u.last_name or "",
            when_iso_now_utc=_now_iso_utc(),
        )

    @app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("dmreadylist"))
    async def _dmready_list(_: Client, m: Message):
        users = store.all() or []
        if not users:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        # Sort by first-mark timestamp if present
        users.sort(key=lambda r: _get(r, "first_marked_iso", "") or _get(r, "first_seen_iso", ""))

        lines = ["✅ *DM-ready users* —"]
        for i, r in enumerate(users, start=1):
            uid = _get(r, "user_id", 0)
            uname = _get(r, "username", "")
            uname_fmt = f"@{uname}" if uname else ""
            first_iso = _get(r, "first_marked_iso", "") or _get(r, "first_seen_iso", "")
            lines.append(f"{i}. {uname_fmt} — `{uid}` — {_parse_any_iso_to_la(first_iso)}")

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
