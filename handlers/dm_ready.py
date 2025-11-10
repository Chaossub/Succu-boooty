# handlers/dm_ready.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

from utils.db import get_db
from utils.config import (
    OWNER_ID,
    DM_READY_COLLECTION,   # e.g. "dm_ready"
)
from utils.logger import log

COLL_NAME = DM_READY_COLLECTION or "dm_ready"
_db = None
_col = None


def _col_ref():
    global _db, _col
    if _col is None:
        _db = get_db()
        _col = _db[COLL_NAME]
        # helpful index; ignore if it exists
        try:
            _col.create_index("user_id", unique=True)
        except Exception:
            pass
    return _col


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💌 I’m DM-ready", callback_data="dmr:toggle")]]
    )


def set_ready(user_id: int, username: Optional[str]) -> Tuple[bool, dict]:
    """
    Upsert 'dm-ready' state (true) and touch timestamps.
    Returns (created_or_updated, doc).
    """
    col = _col_ref()
    update = {
        "$set": {
            "user_id": user_id,
            "username": username,
            "ready": True,
            "last_marked_iso": _now_iso(),
        },
        "$setOnInsert": {"first_marked_iso": _now_iso()},
    }
    res = col.update_one({"user_id": user_id}, update, upsert=True)
    doc = col.find_one({"user_id": user_id}) or {}
    return (res.matched_count == 0, doc)


def clear_all() -> int:
    col = _col_ref()
    res = col.update_many({"ready": True}, {"$set": {"ready": False}})
    return res.modified_count


def is_ready(user_id: int) -> bool:
    doc = _col_ref().find_one({"user_id": user_id}, {"ready": 1})
    return bool(doc and doc.get("ready"))


# --- function other modules import ---
def mark_dm_ready_from_message(message: Message) -> None:
    """
    Public helper for other handlers (e.g. panels) to mark a user as DM-ready
    when appropriate.
    """
    if not message or not message.from_user:
        return
    uid = message.from_user.id
    uname = message.from_user.username
    set_ready(uid, uname)
# -------------------------------------


# -------- Handlers (wired via register(app)) --------
async def _cmd_dmready(client: Client, message: Message):
    if not message.from_user:
        return
    created, doc = set_ready(message.from_user.id, message.from_user.username)
    if created:
        txt = "Marked you as **DM-ready**. Models can safely DM you now. 💌"
    else:
        txt = "You’re **DM-ready**. I refreshed your time stamp. 💌"

    await message.reply_text(txt, reply_markup=_status_kb(), disable_web_page_preview=True)


async def _cb_toggle(client: Client, cq: CallbackQuery):
    if not cq.from_user:
        return
    created, doc = set_ready(cq.from_user.id, cq.from_user.username)
    await cq.answer("Saved. You’re DM-ready. 💌", show_alert=False)

    try:
        await cq.message.edit_reply_markup(_status_kb())
    except Exception:
        # message might be not editable; that's ok
        pass


async def _cmd_dmresetall(client: Client, message: Message):
    if message.from_user and message.from_user.id == OWNER_ID:
        n = clear_all()
        await message.reply_text(f"✅ Cleared DM-ready flag from **{n}** users.")
    else:
        await message.reply_text("Owner only.")


def register(app: Client):
    """
    Required by main.py loader. Wire instance-specific handlers here.
    """
    log.info("✅ handlers.dm_ready registered")
    app.add_handler(filters.command(["dmready"]) & filters.private, _cmd_dmready)
    app.add_handler(filters.callback_query("dmr:toggle"), _cb_toggle)
    app.add_handler(filters.command(["dmresetall"]) & filters.user(OWNER_ID), _cmd_dmresetall)
