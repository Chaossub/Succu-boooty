# dm_foolproof.py — DM-ready dedupe with Mongo persistence + owner tools
import os, json, time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple
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

# announce mode: "first_only" (on first store only) or "always"
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_only").lower().strip()

# --------- Mongo setup ---------
mongo_col = None
mongo_error: str | None = None
if MONGO_URI:
    try:
        _client = MongoClient(MONGO_URI)
        _db = _client[MONGO_DB_NAME]
        mongo_col = _db[DMREADY_COLLECTION]
        mongo_col.create_index("user_id", unique=True, name="uniq_user_id")
        mongo_col.create_index("first_seen", name="idx_first_seen")
    except Exception as e:
        mongo_error = f"{type(e).__name__}: {e}"
        mongo_col = None

# --------- Ephemeral file fallback (not used for announcing) ---------
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

async def _mark_once(uid: int, name: str, username: str) -> str:
    """
    Returns one of:
      - "first"        -> stored in Mongo for the first time
      - "seen"         -> already present in Mongo
      - "db_error"     -> Mongo configured but errored
      - "no_db"        -> Mongo not configured

    NOTE: We only ANNOUNCE on "first". Other states skip announcing to avoid restart spam.
    """
    if mongo_col is not None:
        try:
            mongo_col.insert_one({
                "user_id": uid,
                "name": name,
                "username": username,
                "first_seen": datetime.utcnow()
            })
            return "first"
        except mongo_errors.DuplicateKeyError:
            return "seen"
        except Exception:
            return "db_error"

    # No DB configured
    # (We still store in a local file so /dmreadylist has *something*, but do not announce.)
    fd = _acquire_lock()
    try:
        data = {}
        if DM_FILE.exists():
            try:
                data = json.loads(DM_FILE.read_text())
            except Exception:
                data = {}
        if str(uid) not in data:
            data[str(uid)] = {
                "name": name,
                "username": username,
                "first_seen": datetime.utcnow().isoformat()
            }
            DM_FILE.write_text(json.dumps(data, indent=2))
        return "no_db"
    finally:
        if fd is not None:
            _release_lock(fd)

# --------- Utilities ---------
def _chunk_text(s: str, limit: int = 4000) -> List[str]:
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
    lines = list(body_lines)
    payload = header + ("\n" + "\n".join(lines) if lines else "\n(empty)")
    for part in _chunk_text(payload):
        await message.reply_text(part)

# --------- Handlers ---------
def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        state = await _mark_once(u.id, u.first_name or "Someone", u.username)

        # Announce ONLY when we truly persisted to Mongo the first time.
        if state == "first":
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
        elif state in ("db_error", "no_db") and OWNER_ID:
            # Soft heads-up once per process: DB not working, so we skipped announcement to avoid restart spam.
            # Comment out if you don't want this nudge.
            try:
                await c.send_message(
                    OWNER_ID,
                    "⚠️ DM-ready persistence unavailable "
                    f"({'Mongo error' if state=='db_error' else 'no Mongo configured'}); "
                    "skipped DM-ready announcement to avoid duplicates on restart."
                )
            except Exception:
                pass

        # Show main panel (always)
        ph = await m.reply_text("…")
        await render_main(ph)

    # ---- Owner tools ----
    @app.on_message(filters.private & filters.command("dmready_status"))
    async def _status(c: Client, m: Message):
        if m.from_user.id != OWNER_ID:
            return
        if mongo_col is not None:
            await m.reply_text("✅ Mongo connected.\n"
                               f"DB: <code>{MONGO_DB_NAME}</code>, Collection: <code>{DMREADY_COLLECTION}</code>")
        else:
            await m.reply_text("⚠️ Mongo NOT connected."
                               + (f"\nError: <code>{mongo_error}</code>" if mongo_error else ""))

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
            except Exception as e:
                rows.append(f"⚠️ Could not read from Mongo: {type(e).__name__}")
        else:
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
