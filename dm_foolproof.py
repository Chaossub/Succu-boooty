# dm_foolproof.py — robust /start + DM-ready + admin tools (no locks)
import os
from typing import Dict, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

from req_store import ReqStore
from handlers.panels import render_main

# ---------- Auth ----------
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
# Optional extra admins (comma-separated user IDs)
ADMIN_IDS = {
    int(x.strip())
    for x in (os.getenv("ADMIN_IDS", "") or "").split(",")
    if x.strip().isdigit()
}

# Notify mode: "first_only" or "always"
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

STORE = ReqStore()  # knows if Mongo is active for DM-ready

def _fmt(u):
    name = (u.first_name or "Someone").strip()
    if getattr(u, "last_name", None):
        name = (name + " " + u.last_name).strip()
    handle = f" @{u.username}" if u.username else ""
    return f"{name}{handle}"

def _is_admin(uid: int) -> bool:
    return uid == OWNER_ID or uid in ADMIN_IDS or uid in STORE.list_admins()

def _chunk(text: str, limit: int = 3800) -> List[str]:
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.splitlines():
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = line
        else:
            cur = (cur + "\n" + line) if cur else line
    if cur:
        parts.append(cur)
    return parts

def register(app: Client):

    # ---------- /start ----------
    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user

        # 1) Mark DM-ready; True means state changed (first-ever or after reset)
        changed = False
        try:
            changed = STORE.set_dm_ready_global(u.id, True)
        except Exception:
            changed = False  # never block the panel

        # 2) Announce only if it's truly first time AND persistent (Mongo)
        if changed and STORE.uses_mongo():
            try:
                await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            except RPCError:
                pass
            if _is_admin(OWNER_ID) and DM_READY_NOTIFY_MODE in ("first_only", "always"):
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception:
                    pass

        # 3) Always show the main panel
        ph = await m.reply_text("…")
        await render_main(ph)

    # ---------- /dmready_status ----------
    @app.on_message(filters.private & filters.command("dmready_status"))
    async def _status(c: Client, m: Message):
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 You are not authorized.")
        if STORE.uses_mongo():
            await m.reply_text("✅ DM-ready storage: <b>Mongo (persistent)</b>")
        else:
            await m.reply_text("⚠️ DM-ready storage: <b>JSON (ephemeral)</b>\n"
                               "Add MONGO_URI/MONGO_DB_NAME/DM_READY_COLLECTION to persist.")

    # ---------- /dmready_count ----------
    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 You are not authorized.")
        dm = STORE.list_dm_ready_global()
        await m.reply_text(f"📊 DM-ready unique users: <b>{len(dm)}</b>")

    # ---------- /dmreadylist [N] ----------
    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        """
        Show current Name, @username, and Telegram ID for all DM-ready users.
        Optional limit: /dmreadylist 100  (default 50). Sorted newest first.
        """
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 You are not authorized.")

        dm: Dict[str, dict] = STORE.list_dm_ready_global()
        if not dm:
            return await m.reply_text("🗂 <b>DM-ready (all)</b>\n(empty)")

        # Parse limit if provided
        try:
            parts = (m.text or "").split(maxsplit=1)
            limit = int(parts[1]) if len(parts) > 1 else 50
            if limit <= 0:
                limit = 50
        except Exception:
            limit = 50

        # Sort newest first by 'since'
        sorted_ids = sorted(dm.keys(), key=lambda uid: dm[uid].get("since", 0) or 0, reverse=True)[:limit]
        int_ids = [int(uid) for uid in sorted_ids]

        # Resolve users in batches (Pyrogram can take a list)
        lines: List[str] = []
        step = 100
        for i in range(0, len(int_ids), step):
            chunk = int_ids[i:i+step]
            try:
                users = await c.get_users(chunk)
                if not isinstance(users, list):
                    users = [users]
                by_id = {u.id: u for u in users}
            except Exception:
                by_id = {}

            for uid in chunk:
                u = by_id.get(uid)
                if u:
                    name = (u.first_name or "Someone").strip()
                    if getattr(u, "last_name", None):
                        name = (name + " " + u.last_name).strip()
                    at = f"@{u.username}" if u.username else "(no username)"
                else:
                    name, at = "Unknown", ""
                lines.append(f"• {name} {at} — <code>{uid}</code>")

        text = "🗂 <b>DM-ready (all)</b>\n" + "\n".join(lines)
        for part in _chunk(text):
            await m.reply_text(part)

    # ---------- /dmready_reset <user_id> ----------
    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset(c: Client, m: Message):
        if not _is_admin(m.from_user.id):
            return await m.reply_text("🚫 You are not authorized.")
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await m.reply_text("Usage: /dmready_reset <user_id>")
        try:
            target = int(parts[1])
        except ValueError:
            return await m.reply_text("Provide a numeric user_id.")
        ok = STORE.set_dm_ready_global(target, False)
        await m.reply_text("🔁 Reset." if ok else "No change.")
