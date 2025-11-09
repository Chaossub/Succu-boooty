# handlers/dm_ready.py — single source of truth for /start + DM-ready badge
from __future__ import annotations

import os
from datetime import datetime
import pytz
from dateutil import parser as dtparse

from pyrogram import Client, filters
from pyrogram.types import Message

# centralize the welcome text/keyboard
from handlers.panels import home_text, home_kb

# JSON-first store with dedupe & first-seen semantics
# (uses DMREADY_DB path; survives restarts)
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
LA_TZ = pytz.timezone("America/Los_Angeles")


def _now_iso_utc() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _fmt_la(ts_str: str | None) -> str:
    """Render an ISO-ish timestamp in Los Angeles time (PT)."""
    if not ts_str:
        return "—"
    try:
        dt = dtparse.parse(ts_str)
        if dt.tzinfo is None:
            # assume UTC if naive
            dt = pytz.utc.localize(dt)
        la = dt.astimezone(LA_TZ)
        # Example: 2025-11-08 05:54 PM PT
        return la.strftime("%Y-%m-%d %I:%M %p PT")
    except Exception:
        return ts_str


def _badge_line(user: "pyrogram.types.User", first_seen_iso: str) -> str:
    handle = f"@{user.username}" if getattr(user, "username", None) else ""
    return (
        f"✅ <b>DM-ready:</b> {user.first_name} {handle} — <code>{user.id}</code>\n"
        f"{_fmt_la(first_seen_iso)}"
    )


def register(app: Client):
    @app.on_message(filters.command("start"))
    async def on_start(client: Client, m: Message):
        """
        Single /start entrypoint.
        - Marks user DM-ready (first time only).
        - Posts the green DM-ready badge (with first-seen time, PT).
        - Sends the home panel (text + inline menu).
        """
        user = m.from_user or m.chat
        if not user or getattr(user, "is_bot", False):
            # still send the home panel for safety
            await m.reply_text(home_text(), reply_markup=home_kb(), disable_web_page_preview=True)
            return

        # Dedup: only set first_seen the very first time
        first_iso = store.ensure_dm_ready_first_seen(
            user_id=user.id,
            username=getattr(user, "username", None),
            first_name=user.first_name or "User",
            source="start",
            when_iso=_now_iso_utc(),
        )

        # green badge with first-seen in LA time
        await m.reply_text(
            _badge_line(user, first_iso),
            disable_web_page_preview=True,
        )

        # main panel (welcome + buttons)
        await m.reply_text(
            home_text(),
            reply_markup=home_kb(),
            disable_web_page_preview=True,
        )
