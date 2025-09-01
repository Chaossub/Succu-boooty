# dm_foolproof.py — /start: DM-ready + single welcome panel across replicas
import os
from datetime import datetime, timedelta
from typing import Iterable, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError

from req_store import ReqStore
from handlers.panels import render_main

# ---- Owner + notify mode ----
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

# ---- Mongo for panel lock/session ----
MONGO_URI  = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
MONGO_DB   = os.getenv("MONGO_DB_NAME", "succubot")
_panel_locks = None
_panel_sessions = None
if MONGO_URI:
    try:
        from pymongo import MongoClient, errors as mongo_errors
        _cli = MongoClient(MONGO_URI)
        _db  = _cli[MONGO_DB]
        _panel_locks    = _db["panel_locks"]
        _panel_sessions = _db["panel_sessions"]
        _panel_locks.create_index("user_id", unique=True, name="uniq_lock")
        # TTL on expires_at; value is absolute date, TTL is duration; 0 lets Mongo use document value
        _panel_locks.create_index("expires_at", expireAfterSeconds=0, name="ttl_lock")
        _panel_sessions.create_index("user_id", unique=True, name="uniq_session")
    except Exception:
        _panel_locks = _panel_sessions = None

STORE = ReqStore()

def _fmt(u): return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def _chunk_text(s: str, lim: int = 4000) -> List[str]:
    lines = s.splitlines(); out, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > lim: out.append(cur); cur = ln
        else: cur = (cur + "\n" + ln) if cur else ln
    if cur: out.append(cur); return out

async def _reply_chunked(m: Message, header: str, body: Iterable[str]):
    payload = header + ("\n" + "\n".join(body) if body else "\n(empty)")
    for part in _chunk_text(payload): await m.reply_text(part)

def _acquire_panel_lock(uid: int) -> bool:
    if _panel_locks is None:  # no Mongo -> cannot dedupe cross-replica
        return True  # let one handler proceed; duplicates can occur if multiple replicas
    try:
        _panel_locks.insert_one({
            "user_id": uid,
            "expires_at": datetime.utcnow() + timedelta(seconds=10)
        })
        return True
    except Exception:
        return False

def _release_panel_lock(uid: int):
    if _panel_locks is None: return
    try: _panel_locks.delete_one({"user_id": uid})
    except Exception: pass

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user

        # 1) Mark DM-ready (Mongo via ReqStore). Only announce on first set.
        first_time = False
        try:
            first_time = STORE.set_dm_ready_global(u.id, True)
        except Exception:
            first_time = False

        if first_time:
            try: await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            except RPCError: pass
            if OWNER_ID and DM_READY_NOTIFY_MODE in ("first_only", "always"):
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception: pass

        # 2) Panel: acquire short lock so only one replica renders
        if not _acquire_panel_lock(u.id):
            # Another instance is handling the panel — just exit quietly.
            return
        try:
            # If we have a previous panel from this bot, delete it before sending a fresh one
            last_id = None
            if _panel_sessions is not None:
                try:
                    sess = _panel_sessions.find_one({"user_id": u.id}) or {}
                    last_id = sess.get("msg_id")
                except Exception:
                    last_id = None
            if last_id:
                try: await c.delete_messages(u.id, last_id)
                except Exception: pass

            # Send a fresh panel (placeholder + edit)
            ph = await m.reply_text("…")
            await render_main(ph)

            # Remember the new message id so we can delete it next time
            if _panel_sessions is not None:
                try:
                    _panel_sessions.update_one(
                        {"user_id": u.id},
                        {"$set": {"msg_id": ph.id, "ts": datetime.utcnow()}},
                        upsert=True
                    )
                except Exception:
                    pass
        finally:
            _release_panel_lock(u.id)

    # -------- Owner tools using STORE (Mongo-backed) --------
    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if m.from_user.id != OWNER_ID: return
        await m.reply_text(f"📊 DM-ready unique users: <b>{len(STORE.list_dm_ready_global())}</b>")

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        if m.from_user.id != OWNER_ID: return
        dm = STORE.list_dm_ready_global()
        items = sorted(dm.items(), key=lambda kv: kv[1].get("since", 0), reverse=True)
        lines = [f"• <code>{uid}</code> — since {int(meta.get('since', 0))}" for uid, meta in items]
        await _reply_chunked(m, "🗂 <b>DM-ready (all)</b>", lines)

    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset(c: Client, m: Message):
        if m.from_user.id != OWNER_ID: return
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2: return await m.reply_text("Usage: /dmready_reset <user_id>")
        try: target = int(parts[1])
        except ValueError: return await m.reply_text("Provide a numeric user_id.")
        ok = STORE.set_dm_ready_global(target, False)
        await m.reply_text("🔁 Reset." if ok else "No change.")
