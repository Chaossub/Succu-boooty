# handlers/dm_ready.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

# These exist in your project already
from utils.config import OWNER_ID, DM_READY_COLLECTION, MONGO_DB_NAME
from utils.logger import log

# --- Mongo helper (self-contained; no utils.db) ---
_mongo_db = None

def _get_db():
    """
    Use global builtins.mongo_client if present (your project pattern),
    otherwise create a client from env MONGO_URI.
    """
    global _mongo_db
    if _mongo_db is not None:
        return _mongo_db

    mongo_client = None
    try:
        # many of your modules expose this on builtins
        from builtins import mongo_client as _mc  # type: ignore
        mongo_client = _mc
    except Exception:
        mongo_client = None

    if mongo_client is None:
        from pymongo import MongoClient  # lazy import
        uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGO_URI (or MONGODB_URI) not set")
        # Render + Atlas are happy with TLS defaults
        mongo_client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    db_name = MONGO_DB_NAME or os.environ.get("MONGO_DB", "Succubot")
    _mongo_db = mongo_client[db_name]
    return _mongo_db

# --- collection + small utils ---
COLL_NAME = DM_READY_COLLECTION or "dm_ready"

def _col():
    c = _get_db()[COLL_NAME]
    try:
        c.create_index("user_id", unique=True)
    except Exception:
        pass
    return c

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💌 I’m DM-ready", callback_data="dmr:toggle")]]
    )

# --- core ops ---
def set_ready(user_id: int, username: Optional[str]) -> Tuple[bool, dict]:
    res = _col().update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "username": username,
                "ready": True,
                "last_marked_iso": _now_iso(),
            },
            "$setOnInsert": {"first_marked_iso": _now_iso()},
        },
        upsert=True,
    )
    doc = _col().find_one({"user_id": user_id}) or {}
    return (res.matched_count == 0, doc)

def clear_all() -> int:
    return _col().update_many({"ready": True}, {"$set": {"ready": False}}).modified_count

def is_ready(user_id: int) -> bool:
    d = _col().find_one({"user_id": user_id}, {"ready": 1})
    return bool(d and d.get("ready"))

# --- function other modules import ---
def mark_dm_ready_from_message(message: Message) -> None:
    if not message or not message.from_user:
        return
    set_ready(message.from_user.id, message.from_user.username)

# --- handlers ---
async def _cmd_dmready(client: Client, message: Message):
    if not message.from_user:
        return
    created, _ = set_ready(message.from_user.id, message.from_user.username)
    txt = "Marked you as **DM-ready**. 💌" if created else "You’re **DM-ready**. 💌"
    await message.reply_text(txt, reply_markup=_kb(), disable_web_page_preview=True)

async def _cb_toggle(client: Client, cq: CallbackQuery):
    if not cq.from_user:
        return
    set_ready(cq.from_user.id, cq.from_user.username)
    await cq.answer("Saved. You’re DM-ready. 💌", show_alert=False)
    try:
        await cq.message.edit_reply_markup(_kb())
    except Exception:
        pass  # not editable is fine

async def _cmd_dmresetall(client: Client, message: Message):
    if message.from_user and message.from_user.id == OWNER_ID:
        n = clear_all()
        await message.reply_text(f"✅ Cleared DM-ready from **{n}** users.")
    else:
        await message.reply_text("Owner only.")

def register(app: Client):
    """Required by loader; wire handlers here."""
    log.info("✅ handlers.dm_ready registered")
    app.add_handler(MessageHandler(_cmd_dmready, filters.command(["dmready"]) & filters.private))
    app.add_handler(CallbackQueryHandler(_cb_toggle, filters.regex(r"^dmr:toggle$")))
    app.add_handler(MessageHandler(_cmd_dmresetall, filters.command(["dmresetall"]) & filters.user(OWNER_ID)))
