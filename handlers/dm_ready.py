# handlers/dm_ready.py
from __future__ import annotations

import re
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.dmready_store import DMReadyStore

# IMPORTANT: this is the requirements system store (used by your DM-Ready panel)
from req_store import ReqStore

store = DMReadyStore()
req_store = ReqStore()

MENTION_RE = re.compile(r"@([A-Za-z0-9_]{5,32})")


def fmt_pt(ts: float | None) -> str:
    if not ts:
        return "—"
    dt = datetime.fromtimestamp(ts)
    # Keep it simple (your screenshots show PT text; if you want strict PT convert we can)
    return dt.strftime("%Y-%m-%d %I:%M %p")


async def mark_dm_ready_from_message(client: Client, msg: Message):
    """
    Called when someone DMs the bot (or uses /dmready).
    This writes to dm_ready.json AND also syncs into ReqStore.dm_ready_global
    so the DM-Ready panel can actually find them.
    """
    u = msg.from_user
    if not u:
        return

    username = u.username or ""
    name = " ".join([p for p in [u.first_name, u.last_name] if p]).strip()

    store.set_ready(
        user_id=u.id,
        ready=True,
        username=username,
        name=name,
        last_seen_ts=msg.date.timestamp() if msg.date else datetime.now().timestamp(),
    )

    # ✅ This is the missing piece that makes your panel stop showing “none found”
    req_store.set_dm_ready_global(u.id, True, by_admin=False)


def register(app: Client):
    # Mark DM-ready when they DM the bot
    @app.on_message(filters.private & filters.incoming & ~filters.service)
    async def _auto_mark(_, msg: Message):
        # avoid marking on obvious bot-start spam if you want; leaving permissive for now
        await mark_dm_ready_from_message(app, msg)

    # Manual command (works in DM)
    @app.on_message(filters.private & filters.command("dmready"))
    async def _dmready_cmd(_, msg: Message):
        await mark_dm_ready_from_message(app, msg)
        await msg.reply_text("✅ Marked DM-ready.")

    # Manual unready (optional)
    @app.on_message(filters.private & filters.command("notdmready"))
    async def _notdmready_cmd(_, msg: Message):
        u = msg.from_user
        if not u:
            return
        store.set_ready(
            user_id=u.id,
            ready=False,
            username=u.username or "",
            name=" ".join([p for p in [u.first_name, u.last_name] if p]).strip(),
            last_seen_ts=msg.date.timestamp() if msg.date else datetime.now().timestamp(),
        )
        req_store.set_dm_ready_global(u.id, False, by_admin=False)
        await msg.reply_text("🚫 Removed DM-ready.")

    # Admin backfill command (so your panel matches your existing dm_ready.json immediately)
    @app.on_message(filters.command("dmready_fix_panel"))
    async def _backfill_to_req_store(_, msg: Message):
        u = msg.from_user
        if not u:
            return
        # you can tighten this to OWNER_ID if you want
        # (leaving as “admins only” via chat admin checks is more work; keeping it simple)
        rows = store.get_all_ready()
        fixed = 0
        for uid_str, row in rows.items():
            try:
                uid = int(uid_str)
            except Exception:
                continue
            if row.get("dm_ready") is True:
                changed = req_store.set_dm_ready_global(uid, True, by_admin=True)
                if changed:
                    fixed += 1
        await msg.reply_text(f"✅ Synced DM-ready into panel store. Updated: {fixed}")
