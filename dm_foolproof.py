# dm_foolproof.py
import os, json, asyncio, tempfile
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from handlers.panels import render_main

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DM_FILE = DATA_DIR / "dm_ready.json"
_lock = asyncio.Lock()            # process-level debounce
_seen = set()                     # in-memory debounce during one run

def _load():
    try:
        if DM_FILE.exists():
            return json.loads(DM_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"users": {}}

def _atomic_save(payload: dict):
    tmp = DM_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DM_FILE)

async def _mark_once(user_id: int, name: str, username: str|None) -> bool:
    async with _lock:
        store = _load()
        key = str(user_id)
        if key in store["users"]:
            return False
        store["users"][key] = {
            "name": name,
            "username": username or "",
            "since": datetime.utcnow().isoformat() + "Z",
        }
        _atomic_save(store)
        return True

def _fmt(u): return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        new = False
        # in-memory fast path (prevents double-fire in same second)
        if u.id not in _seen:
            _seen.add(u.id)
            new = await _mark_once(u.id, u.first_name or "Someone", u.username)

        if new:
            await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            if OWNER_ID:
                try:
                    await c.send_message(OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>")
                except Exception:
                    pass

        # show main menu (edit-in-place)
        ph = await m.reply_text("…")
        await render_main(ph)
