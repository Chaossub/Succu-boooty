# handlers/dm_ready.py
from __future__ import annotations
import os, json, time, logging
from pathlib import Path
from typing import Dict, Set

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

log = logging.getLogger("dm_ready")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

# --- persistence (survives restarts) ---
DATA_DIR = Path("data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
READY_FILE = DATA_DIR / "dm_ready.json"       # { "<user_id>": {...} }
WELC_FILE  = DATA_DIR / "dm_welcomed.json"    # { "<user_id>": true }

def _load_json(p: Path) -> Dict:
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_json(p: Path, obj: Dict):
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(p)

def _fmt_owner_line(user) -> str:
    uname = f"@{user.username}" if getattr(user, "username", None) else ""
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    return f"✅ <b>DM-ready</b>: {user.first_name or 'User'} {uname}\n<code>{user.id}</code> • {ts}Z"

# --- ultra-small de-dup to kill double /start triggers ---
_INFLIGHT: Dict[int, float] = {}      # user_id -> last_ts
DEDUP_WINDOW = 2.0                    # seconds

def _already_processing(uid: int) -> bool:
    now = time.time()
    last = _INFLIGHT.get(uid, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _INFLIGHT[uid] = now
    # prune old
    for k, ts in list(_INFLIGHT.items()):
        if now - ts > 5 * DEDUP_WINDOW:
            _INFLIGHT.pop(k, None)
    return False

async def _mark_dm_ready_once_and_maybe_welcome(client: Client, m: Message):
    if not m.from_user or m.from_user.is_bot:
        return
    u = m.from_user
    if _already_processing(u.id):
        return  # second handler fired within the window → ignore

    uid_str = str(u.id)

    ready = _load_json(READY_FILE)
    welc  = _load_json(WELC_FILE)

    if uid_str not in ready:
        ready[uid_str] = {
            "id": u.id,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "username": u.username or "",
            "ts": int(time.time()),
        }
        _save_json(READY_FILE, ready)
        if OWNER_ID:
            try:
                await client.send_message(OWNER_ID, _fmt_owner_line(u))
            except Exception:
                pass

    if not welc.get(uid_str, False):
        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True
        )
        welc[uid_str] = True
        _save_json(WELC_FILE, welc)

def register(app: Client):
    async def _remove(uid: int):
        try:
            uid_str = str(uid)
            ready = _load_json(READY_FILE)
            if uid_str in ready:
                del ready[uid_str]
                _save_json(READY_FILE, ready)
        except Exception:
            pass
    setattr(app, "_succu_dm_store_remove", _remove)

    @app.on_message(filters.private & filters.command("start"))
    async def _start(client: Client, m: Message):
        await _mark_dm_ready_once_and_maybe_welcome(client, m)

    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def _dmreadylist(client: Client, m: Message):
        if not m.from_user or m.from_user.id != OWNER_ID:
            return
        data = _load_json(READY_FILE)
        if not data:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")
        rows = list(data.values()); rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
        lines = ["✅ <b>DM-ready users</b>"]
        for i, r in enumerate(rows, start=1):
            uname = f"@{r.get('username')}" if r.get("username") else ""
            lines.append(f"{i}. {r.get('first_name','User')} {uname} — <code>{r.get('id')}</code>")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.private & filters.command("dmreadyclear"))
    async def _dmreadyclear(client: Client, m: Message):
        if not m.from_user or m.from_user.id != OWNER_ID:
            return
        _save_json(READY_FILE, {})
        await m.reply_text("🧹 Cleared DM-ready list.")
