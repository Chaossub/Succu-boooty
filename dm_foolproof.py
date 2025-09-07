# dm_foolproof.py
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any

from pyrogram import Client, filters
from pyrogram.types import Message

from pymongo import MongoClient

# Mongo connection
_MONGO_URL = os.getenv("MONGO_URL")
if not _MONGO_URL:
    raise RuntimeError("MONGO_URL is required in ENV for DM-ready persistence.")
_DB_NAME = os.getenv("MONGO_DB", "succubot")

_mcli = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=10000)
_db = _mcli[_DB_NAME]
col_dm = _db.get_collection("dm_ready")

# Small helpers
def _now_ts() -> int:
    return int(time.time())

def _fmt_user_line(u) -> str:
    name = u.first_name or u.last_name or "Someone"
    uname = f"@{u.username}" if u.username else ""
    return f"{name} {uname}".strip()

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
        [_btn("💕 Menu", "menu")],
        [_btn("👑 Contact Admins", "admins")],
        [_btn("🔥 Find Our Models Elsewhere", "models")],
        [_btn("❓ Help", "help")],
    ])

async def _send_main_panel(msg: Message):
    await msg.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)

async def _mark_dm_ready_once(user_id: int, name: str, username: Optional[str]):
    # Store user in Mongo only once
    existing = col_dm.find_one({"user_id": user_id})
    if existing:
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

    @app.on_message(filters.command("dmreadylist"))
    async def _dmready_list(c: Client, m: Message):
        users = list(col_dm.find())
        if not users:
            await m.reply_text("📭 No DM-ready users yet.")
            return
        lines = ["📋 DM-ready (all)"]
        for u in users:
            uname = f"@{u['username']}" if u.get("username") else ""
            lines.append(f"- {u['name']} {uname}\n   id: {u['user_id']} — since {datetime.utcfromtimestamp(u['ts']).isoformat()} UTC")
        await m.reply_text("\n".join(lines))

    @app.on_message(filters.private & ~filters.service)
    async def _on_any_private(c: Client, m: Message):
        if not m.from_user:
            return
        await _mark_dm_ready_once(
            m.from_user.id,
            m.from_user.first_name or "Someone",
            m.from_user.username
        )
