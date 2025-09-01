# dm_foolproof.py — DM-ready + /start dedupe with MongoDB persistence
import os
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient, errors

from handlers.panels import render_main

# ---- ENV ----
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Mongo settings (works with same cluster you use elsewhere)
MONGO_URI            = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
MONGO_DB_NAME        = os.getenv("MONGO_DB_NAME", "succubot")
DM_READY_COLLECTION  = os.getenv("DM_READY_COLLECTION", "dm_ready")

# ---- DB ----
client = MongoClient(MONGO_URI) if MONGO_URI else None
col = None
if client:
    db = client[MONGO_DB_NAME]
    col = db[DM_READY_COLLECTION]
    # Unique user_id so duplicates across restarts/processes are prevented
    try:
        col.create_index("user_id", unique=True)
    except Exception:
        pass

def _fmt(u):
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

async def _mark_once(uid: int, name: str, username: str) -> bool:
    """
    Returns True only the first time we ever see this user.
    Persists to Mongo so it survives restarts/deploys and works across replicas.
    """
    if not col:
        # No DB configured -> fallback (will NOT survive restarts)
        return True

    try:
        col.insert_one({
            "user_id": uid,
            "name": name,
            "username": username,
            "first_seen": datetime.utcnow()
        })
        return True  # first time
    except errors.DuplicateKeyError:
        return False  # seen before
    except Exception:
        # If DB is temporarily down, act conservative (avoid spam)
        return False

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        first_time = await _mark_once(u.id, u.first_name or "Someone", u.username)

        if first_time:
            await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            if OWNER_ID:
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception:
                    pass

        # Always show the main panel (edit-in-place placeholder)
        ph = await m.reply_text("…")
        await render_main(ph)

    # Optional: owner-only test/reset helpers
    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset_one(c: Client, m: Message):
        if not col or m.from_user.id != OWNER_ID:
            return
        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await m.reply_text("Usage: /dmready_reset <user_id>")
            return
        try:
            target = int(parts[1])
        except ValueError:
            await m.reply_text("Provide a numeric user_id.")
            return
        col.delete_one({"user_id": target})
        await m.reply_text(f"🔁 Reset DM-ready for <code>{target}</code>.")

    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if not col or m.from_user.id != OWNER_ID:
            return
        await m.reply_text(f"📊 DM-ready unique users: <b>{col.estimated_document_count()}</b>")
