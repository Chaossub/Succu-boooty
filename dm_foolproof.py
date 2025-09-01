# dm_foolproof.py
import os, json, asyncio, time
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from handlers.panels import render_main

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DM_FILE = DATA_DIR / "dm_ready.json"

# Cross-process lock to kill duplicate “DM-ready” + double welcome
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

async def _mark_once(uid: int, name: str, username: str):
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
            "ts": datetime.utcnow().isoformat()
        }
        DM_FILE.write_text(json.dumps(data, indent=2))
        return True
    finally:
        if fd is not None:
            _release_lock(fd)

def _fmt(u): 
    return f"{u.first_name or 'Someone'}" + (f" @{u.username}" if u.username else "")

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        u = m.from_user
        new = await _mark_once(u.id, u.first_name or "Someone", u.username)

        if new:
            await m.reply_text(f"✅ DM-ready — {_fmt(u)}")
            if OWNER_ID:
                try:
                    await c.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
                except Exception:
                    pass

        # Show main menu (edit in place)
        ph = await m.reply_text("…")
        await render_main(ph)
