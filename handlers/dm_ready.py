# handlers/dm_ready.py
from __future__ import annotations
import os
from datetime import datetime, timezone
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

# ── Config
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
LA_TZ = pytz.timezone("America/Los_Angeles")

# ── Helpers
def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _fmt_la_from_iso(iso_str: str | None) -> str:
    if not iso_str:
        return "-"
    try:
        if iso_str.endswith("Z"):
            dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        else:
            dt_utc = datetime.fromisoformat(iso_str)
        dt_la = dt_utc.astimezone(LA_TZ)
        return dt_la.strftime("%Y-%m-%d %I:%M %p PT").lstrip("0")
    except Exception:
        return iso_str

# ── Register
def register(app: Client) -> None:

    @app.on_message(filters.private & filters.command("start"))
    async def _on_start(c: Client, m: Message):
        """
        Marks user as DM-ready if not already marked (persistent via JSON).
        Returns first seen timestamp (never changes on restarts).
        """
        u = m.from_user
        if not u:
            return

        first_seen_iso = store.ensure_dm_ready_first_seen(
            user_id=u.id,
            username=u.username or "",
            first_name=u.first_name or "",
            last_name=u.last_name or "",
            when_iso_now_utc=_now_iso_utc(),
        )

        # Convert UTC time to LA for display
        first_seen_la = _fmt_la_from_iso(first_seen_iso)
        name = (u.first_name or "").strip()
        uname = f"@{u.username}" if u.username else ""
        badge = f"✅ DM-ready: {name} {uname} — {u.id}\n{first_seen_la}"
        await m.reply_text(badge)

    @app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("dmreadylist"))
    async def _dmready_list(_: Client, m: Message):
        """
        Owner-only list of all DM-ready users, sorted by first seen time.
        """
        all_users = store.all()
        if not all_users:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        def _sort_key(rec):
            val = getattr(rec, "first_marked_iso", "") or ""
            return (val == "", val)

        all_users.sort(key=_sort_key)

        lines = ["✅ *DM-ready users* —"]
        for i, r in enumerate(all_users, start=1):
            uname = f"@{r.username}" if r.username else ""
            lines.append(
                f"{i}. {uname} — `{r.user_id}` — {_fmt_la_from_iso(r.first_marked_iso)}"
            )

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
