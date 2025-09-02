# dm_foolproof.py — robust /start + DM-ready + owner tools (no locks)
import os
from typing import Iterable, List, Dict
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

from req_store import ReqStore
from handlers.panels import render_main

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

STORE = ReqStore()  # knows if Mongo is active for DM-ready

def _fmt(u):
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user

        # 1) Mark DM-ready; "changed" means first-ever (or after a reset)
        changed = False
        try:
            changed = STORE.set_dm_ready_global(u.id, True)
        except Exception:
            changed = False  # never block the panel

        # 2) Announce only if this was truly the first store AND it's persistent (Mongo).
        if changed and STORE.uses_mongo():
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

        # 3) Always show the main panel (no early exit)
        ph = await m.reply_text("…")
        await render_main(ph)

    # ---------- Owner tools ----------
    @app.on_message(filters.private & filters.command("dmready_status"))
    async def _status(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        await m.reply_text(
            "✅ DM-ready storage: <b>Mongo (persistent)</b>"
            if STORE.uses_mongo()
            else "⚠️ DM-ready storage: <b>JSON (ephemeral)</b>\nAdd MONGO_URI/MONGO_DB_NAME/DM_READY_COLLECTION to persist."
        )

    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        count = len(STORE.list_dm_ready_global())
        await m.reply_text(f"📊 DM-ready unique users: <b>{count}</b>")

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        """
        Show: Name, @username, Telegram ID — newest first.
        Names/usernames are resolved live so they're always current.
        """
        if m.from_user.id != OWNER_ID:
            return

        dm: Dict[str, dict] = STORE.list_dm_ready_global()
        if not dm:
            return await m.reply_text("🗂 <b>DM-ready (all)</b>\n(empty)")

        # Sort newest first by 'since'
        pairs = sorted(dm.items(), key=lambda kv: kv[1].get("since", 0), reverse=True)
        ids = [int(uid) for uid, _ in pairs]

        # Resolve in batches to avoid oversized requests
        lines: List[str] = []
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            chunk = ids[i : i + batch_size]
            try:
                users = await c.get_users(chunk)  # returns list of Users
                by_id = {u.id: u for u in (users if isinstance(users, list) else [users])}
            except Exception:
                by_id = {}

            for uid in chunk:
                u = by_id.get(uid)
                if u:
                    name = (u.first_name or "Someone").strip()
                    if u.last_name:
                        name = (name + " " + u.last_name).strip()
                    at = f"@{u.username}" if u.username else "(no username)"
                else:
                    name, at = "Someone", "(unknown)"
                lines.append(f"• {name} {at} — <code>{uid}</code>")

        text = "🗂 <b>DM-ready (all)</b>\n" + "\n".join(lines)
        # Telegram 4096 char limit — send in chunks if needed
        while len(text) > 3800:
            cut = text.rfind("\n", 0, 3800)
            await m.reply_text(text[:cut])
            text = text[cut+1:]
        await m.reply_text(text)

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
