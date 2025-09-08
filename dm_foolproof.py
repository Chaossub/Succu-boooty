# dm_foolproof.py
import os, time
from datetime import datetime, timezone
from typing import Optional
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import MessageNotModified, BadRequest
from pymongo import MongoClient

# === Mongo connection ===
_MONGO_URL = os.getenv("MONGO_URL")
if not _MONGO_URL:
    raise RuntimeError("MONGO_URL is required in ENV for DM-ready persistence.")
_DB_NAME = os.getenv("MONGO_DB", "succubot")
_mcli = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=10000)
_db = _mcli[_DB_NAME]
col_dm = _db.get_collection("dm_ready")

def _now_ts() -> int:
    return int(time.time())

def _hms(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s and not parts: parts.append(f"{s}s")
    return " ".join(parts) or "0s"

def _welcome_text() -> str:
    return (
        "🔥 Welcome to SuccuBot 🔥\n"
        "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, "
        "flirty, and flowing.\n\n"
        "✨ Use the menu below to navigate!"
    )

def _main_kb():
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    def _btn(text, data): return InlineKeyboardButton(text, callback_data=data)
    return InlineKeyboardMarkup([
        [_btn("💕 Menus", "menus")],
        [_btn("👑 Contact Admins", "admins")],
        [_btn("🔥 Find Our Models Elsewhere", "models")],
        [_btn("❓ Help", "help")],
    ])

async def _send_main_panel(msg: Message):
    await msg.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)

async def _mark_dm_ready_once(user_id: int, name: str, username: Optional[str]):
    if col_dm.find_one({"user_id": user_id}):
        return
    col_dm.insert_one({
        "user_id": user_id,
        "name": name,
        "username": username,
        "ts": _now_ts()
    })

def register(app: Client):
    @app.on_message(filters.command("start") & filters.private)
    async def _on_start(c: Client, m: Message):
        await _send_main_panel(m)

    # Universal "Home" so any panel can jump back to start
    @app.on_callback_query(filters.regex(r"^home$"))
    async def _go_home(c: Client, q):
        try:
            await q.message.edit_text(
                _welcome_text(),
                reply_markup=_main_kb(),
                disable_web_page_preview=True
            )
        except MessageNotModified:
            try:
                await q.message.edit_reply_markup(_main_kb())
            except MessageNotModified:
                pass
        except Exception:
            await _send_main_panel(q.message)

    @app.on_message(filters.command("dmreadylist"))
    async def _dmready_list(c: Client, m: Message):
        raw = list(col_dm.find().sort("ts", 1))
        users = [u for u in raw if "user_id" in u]  # skip malformed docs

        if not users:
            await m.reply_text("📭 No DM-ready users yet.")
            return

        now = _now_ts()
        lines = ["📋 DM-ready (all)"]
        for u in users:
            uid = u.get("user_id")
            name = u.get("name") or "Someone"
            uname = f"@{u.get('username')}" if u.get("username") else ""
            ts = int(u.get("ts", now))
            age = _hms(now - ts)
            try:
                since = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                since = "?"
            lines.append(f"- {name} {uname}\n   id: {uid} — since {since} ({age})")
        await m.reply_text("\n".join(lines))

    # Mark anyone who DMs the bot as DM-ready (persists)
    @app.on_message(filters.private & ~filters.service)
    async def _on_any_private(c: Client, m: Message):
        if not m.from_user:
            return
        await _mark_dm_ready_once(
            m.from_user.id,
            m.from_user.first_name or "Someone",
            m.from_user.username
        )

