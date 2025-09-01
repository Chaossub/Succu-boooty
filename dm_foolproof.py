# dm_foolproof.py — DM-ready dedupe (Mongo) + owner tools, with full /dmreadylist
import os, json, time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from pymongo import MongoClient, errors as mongo_errors

from handlers.panels import render_main

# --------- ENV ---------
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

MONGO_URI          = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
MONGO_DB_NAME      = os.getenv("MONGO_DB_NAME", "succubot")
DMREADY_COLLECTION = os.getenv("DM_READY_COLLECTION", "dm_ready")

DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

# --------- Mongo setup ---------
mongo_col = None
if MONGO_URI:
    try:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
        mongo_col = _db[DMREADY_COLLECTION]
        mongo_col.create_index("user_id", unique=True, name="uniq_user_id")
        mongo_col.create_index("first_seen", name="idx_first_seen")
    except Exception:
        mongo_col = None  # fall back to file

# --------- Ephemeral file fallback (only if mongo isn't available) ---------
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DM_FILE = DATA_DIR / "dm_ready.json"
LOCK_FILE = DATA_DIR / "dm_ready.lock"

def _acquire_lock(timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return fd
        except FileExistsError:
            time.sleep(0.05)
    return None

def _release_lock(fd):
    try:
        os.close(fd)
        os.remove(LOCK_FILE)
    except Exception:
        pass

def _fmt_user(u):
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

async def _mark_once(uid: int, name: str, username: str) -> bool:
    """
    True only the first time we see this user.
    Uses Mongo (persistent); falls back to local JSON if Mongo is down.
    """
    if mongo_col is not None:
        try:
            mongo_col.insert_one({
                "user_id": uid,
                "name": name,
                "username": username,
                "first_seen": datetime.utcnow()
            })
            return True
        except mongo_errors.DuplicateKeyError:
            return False
        except Exception:
            pass  # fall through to file fallback

    # Fallback: local JSON (ephemeral)
    fd = _acquire_lock()
    try:
        data = {}
        if DM_FILE.exists():
            try:
                data = json.loads(DM_FILE.read_text())
            except Exception:
                data = {}
        if str(uid) in data:
            return False
        data[str(uid)] = {
            "name": name,
            "username": username,
            "first_seen": datetime.utcnow().isoformat()
        }
        DM_FILE.write_text(json.dumps(data, indent=2))
        return True
    finally:
        if fd is not None:
            _release_lock(fd)

# --------- Utilities ---------
def _chunk_text(s: str, limit: int = 4000) -> List[str]:
    """Split a long string into Telegram-safe chunks (slightly under 4096)."""
    lines = s.splitlines()
    out, cur = [], ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            out.append(cur)
            cur = ln
        else:
            cur = (cur + "\n" + ln) if cur else ln
    if cur:
        out.append(cur)
    return out

async def _reply_chunked(message: Message, header: str, body_lines: Iterable[str]):
    """Reply with a header + potentially many lines, chunked safely."""
    lines = list(body_lines)
    if not lines:
        await message.reply_text(header + "\n(empty)")
        return
    payload = header + "\n" + "\n".join(lines)
    for part in _chunk_text(payload):
        await message.reply_text(part)

# --------- Handlers ---------
def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        first_time = await _mark_once(u.id, u.first_name or "Someone", u.username)

        if first_time:
            try:
                await m.reply_text(f"✅ DM-ready — {_fmt_user(u)}")
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

    # ---- Owner tools ----
    @app.on_message(filters.private & filters.command("dmready_count"))
    async def _count(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        if mongo_col is not None:
            try:
                count = mongo_col.estimated_document_count()
            except Exception:
                count = 0
        else:
            if DM_FILE.exists():
                try:
                    count = len(json.loads(DM_FILE.read_text()))
                except Exception:
                    count = 0
            else:
                count = 0
        await m.reply_text(f"📊 DM-ready unique users: <b>{count}</b>")

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _list_all(c: Client, m: Message):
        """
        List ALL DM-ready users: name, @username, Telegram ID.
        Sorted by newest first. Owner-only.
        """
        if m.from_user.id != OWNER_ID:
            return

        rows: List[str] = []
        if mongo_col is not None:
            try:
                cursor = mongo_col.find({}, {"_id": 0}).sort("first_seen", -1)
                for doc in cursor:
                    name = (doc.get("name") or "Someone").strip()
                    un = (doc.get("username") or "").strip()
                    uid = doc.get("user_id")
                    at = f"@{un}" if un else "(no username)"
                    rows.append(f"• {name} {at} — <code>{uid}</code>")
            except Exception:
                rows.append("⚠️ Could not read from Mongo.")
        else:
            # File fallback
            try:
                data = json.loads(DM_FILE.read_text()) if DM_FILE.exists() else {}
                items = sorted(
                    data.items(),
                    key=lambda kv: kv[1].get("first_seen", kv[1].get("ts", "")),
                    reverse=True
                )
                for uid, doc in items:
                    name = (doc.get("name") or "Someone").strip()
                    un = (doc.get("username") or "").strip()
                    at = f"@{un}" if un else "(no username)"
                    rows.append(f"• {name} {at} — <code>{uid}</code>")
            except Exception:
                rows.append("⚠️ No local DM-ready file.")

        await _reply_chunked(m, "🗂 <b>DM-ready (all)</b>", rows)

    @app.on_message(filters.private & filters.command("dmready_reset"))
    async def _reset(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
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

        ok = False
        if mongo_col is not None:
            try:
                mongo_col.delete_one({"user_id": target})
                ok = True
            except Exception:
                ok = False
        else:
            try:
                data = json.loads(DM_FILE.read_text()) if DM_FILE.exists() else {}
                if str(target) in data:
                    del data[str(target)]
                    DM_FILE.write_text(json.dumps(data, indent=2))
                ok = True
            except Exception:
                ok = False

        await m.reply_text(("🔁 Reset DM-ready for <code>{}</code>.".format(target)) if ok else "⚠️ Reset failed.")
