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
        [_btn("💕 Menu", "nav:menus")],
        [_btn("👑 Contact Admins", "nav:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "nav:find")],
        [_btn("❓ Help", "nav:help")],
    ])

async def _send_main_panel(msg: Message):
    await msg.reply_text(_welcome_text(), reply_markup=_main_kb(), disable_web_page_preview=True)

async def _mark_dm_ready_once(user_id: int, name: str, username: Optional[str]) -> bool:
    """
    Returns True only the first time we see this user (i.e., when we insert).
    On subsequent /start calls it returns False so we don't spam the DM-ready line.
    """
    existing = col_dm.find_one({"_id": user_id})
    if existing:
        # Already recorded; update name/username if changed, don't resend banner
        upd: Dict[str, Any] = {}
        if existing.get("name") != name:
            upd["name"] = name
        if existing.get("username") != username:
            upd["username"] = username
        if upd:
            col_dm.update_one({"_id": user_id}, {"$set": upd})
        return False

    col_dm.insert_one({
        "_id": user_id,
        "name": name,
        "username": username,
        "since": _now_ts(),
        "ready": True
    })
    return True


# -----------------------------
# Register into Pyrogram app
# -----------------------------
def register(app: Client):

    # /start — single place that handles DM-ready-once + shows main panel
    @app.on_message(filters.command("start"))
    async def start_handler(_, m: Message):
        u = m.from_user
        name = u.first_name or u.last_name or "Someone"
        username = u.username

        first_time = await _mark_dm_ready_once(u.id, name, username)

        if first_time:
            line = f"✅ DM-ready — {name} " + (f"@{username}" if username else "")
            await m.reply_text(line, disable_web_page_preview=True)

        # Always render the main menu block (only once per /start call)
        await _send_main_panel(m)

    # /dmreadylist — show current DM-ready users with name, @user, id, since
    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list_handler(_, m: Message):
        rows = []
        for doc in col_dm.find({"ready": True}).sort("since", 1):
            nm = doc.get("name") or "Someone"
            un = f"@{doc.get('username')}" if doc.get("username") else ""
            uid = doc["_id"]
            since = datetime.utcfromtimestamp(int(doc.get("since", 0))).strftime("%Y-%m-%d %H:%M:%S UTC")
            rows.append(f"• {nm} {un}\n  id: {uid} — since {since}")

        if not rows:
            await m.reply_text("📭 No one is marked DM-ready.")
            return

        text = "📋 **DM-ready (all)**\n" + "\n\n".join(rows)
        await m.reply_text(text, disable_web_page_preview=True)
