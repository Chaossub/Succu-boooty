# dm_foolproof.py — /start flow that marks DM-ready via ReqStore (Mongo-backed)
import os
from datetime import datetime
from typing import Iterable, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

from req_store import ReqStore
from handlers.panels import render_main

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

STORE = ReqStore()

def _fmt(u): 
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def _chunk_text(s: str, lim: int = 4000) -> List[str]:
    lines = s.splitlines()
    out, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > lim:
            out.append(cur); cur = ln
        else:
            cur = (cur + "\n" + ln) if cur else ln
    if cur: out.append(cur)
    return out

async def _reply_chunked(m: Message, header: str, body: Iterable[str]):
    payload = header + ("\n" + "\n".join(body) if body else "\n(empty)")
    for part in _chunk_text(payload):
        await m.reply_text(part)

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        # Mark DM-ready in the store; returns True if state changed (first time).
        changed = STORE.set_dm_ready_global(u.id, True)

        if changed:
            try:
                await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            except RPCError:
                pass
            if OWNER_ID and DM_READY_NOTIFY_MODE in ("first_only", "always"):
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception:
                    pass

        ph = await m.reply_text("…")
        await render_main(ph)

    # Owner tools, backed by STORE
    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        count = len(STORE.list_dm_ready_global())
        await m.reply_text(f"📊 DM-ready unique users: <b>{count}</b>")

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        out = []
        # If you want names/usernames, you can keep a side cache elsewhere; ReqStore DM-ready map only stores flags.
        # We'll list IDs here; augment as needed where you gather profiles.
        dm = STORE.list_dm_ready_global()
        # Newest first by 'since'
        items = sorted(dm.items(), key=lambda kv: kv[1].get("since", 0), reverse=True)
        for uid, meta in items:
            out.append(f"• <code>{uid}</code> — since {int(meta.get('since', 0))}")
        await _reply_chunked(m, "🗂 <b>DM-ready (all)</b>", out)

    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: /dmready_reset <user_id>")
        try:
            target = int(parts[1])
        except ValueError:
            return await m.reply_text("Provide a numeric user_id.")
        ok = STORE.set_dm_ready_global(target, False)
        await m.reply_text("🔁 Reset." if ok else "No change.")

