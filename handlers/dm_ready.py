# handlers/dm_ready.py
from __future__ import annotations

import os
from datetime import datetime, timezone
import pytz

from pyrogram import Client, filters
from pyrogram.types import Message

# JSON-backed store
from utils.dmready_store import global_store as store


# ── Config
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
LA_TZ = pytz.timezone("America/Los_Angeles")


# ── Time helpers
def _now_iso_utc() -> str:
    """UTC now as ISO-8601 with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_la_from_iso(iso_str: str | None) -> str:
    """
    Convert an ISO timestamp (UTC or with any offset) to America/Los_Angeles,
    and format as 'YYYY-MM-DD hh:mm AM/PM PT'.
    """
    if not iso_str:
        return "-"
    # Accept '...Z' or with offset
    try:
        if iso_str.endswith("Z"):
            dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        else:
            dt_utc = datetime.fromisoformat(iso_str)
        dt_la = dt_utc.astimezone(LA_TZ)
        return dt_la.strftime("%Y-%m-%d %I:%M %p PT").lstrip("0")
    except Exception:
        return iso_str


# ── Register bot handlers
def register(app: Client) -> None:
    @app.on_message(filters.private & filters.command("start"))
    async def _on_start(c: Client, m: Message):
        """
        Mark the user DM-ready the FIRST time only (JSON persists across restarts).
        Sends a one-line badge with LA time every /start, but the stored 'first seen'
        never changes—so no duplicates in the list.
        """
        u = m.from_user
        if not u:
            return

        rec = store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
            first_name=u.first_name or "",
            last_name=u.last_name or "",
            when_iso_now_utc=_now_iso_utc(),
        )

        # Show a small one-line badge (for your sanity in chat),
        # with the stored FIRST time in LA time.
        first_seen_la = _fmt_la_from_iso(rec.get("first_marked_iso"))
        name = (rec.get("first_name") or "").strip()
        uname = (rec.get("username") or "").strip()
        handle = f"@{uname}" if uname else ""
        badge = f"✅ DM-ready: {name} {handle} — {rec.get('user_id')}\n{first_seen_la}"
        await m.reply_text(badge)

        # Your welcome/menu panel likely lives elsewhere; keep this lightweight here.

    @app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("dmreadylist"))
    async def _dmready_list(_: Client, m: Message):
        """
        Owner-only: list all DM-ready users, sorted by FIRST seen time.
        Shows LA-local time, exactly once per user.
        """
        all_users = store.all()  # returns list of dicts
        if not all_users:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        # Sort by first seen ISO (missing values go last)
        def _key(rec):
            val = rec.get("first_marked_iso") or ""
            # put empty at the end
            return (val == "", val)

        all_users.sort(key=_key)

        lines = ["✅ *DM-ready users* —"]
        for i, r in enumerate(all_users, start=1):
            name = (r.get("first_name") or "").strip()
            uname = (r.get("username") or "").strip()
            handle = f"@{uname}" if uname else ""
            uid = r.get("user_id")
            first_seen_la = _fmt_la_from_iso(r.get("first_marked_iso"))
            lines.append(f"{i}. {name} {handle} — `{uid}` — {first_seen_la}")

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
