# handlers/dmready_watch.py
# Remove DM-ready flag when a member leaves / is kicked / banned
# from watched group(s).

import os
import time
from typing import Set, Tuple, Dict

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, User
from pyrogram.enums import ChatMemberStatus, ChatType

from utils.dmready_store import DMReadyStore

# Parse group IDs from env (comma/semicolon spaced).
def _parse_ids(val: str) -> Set[int]:
    out: Set[int] = set()
    for tok in (val or "").replace(";", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.add(int(tok))
        except Exception:
            pass
    return out

# You can override via env; default includes the ID you gave me.
DMREADY_WATCH_IDS: Set[int] = _parse_ids(os.getenv("DMREADY_WATCH_IDS", "")) or {-1002823762054}

# (very light) de-duplication so we don't double-handle join/leave pairs
_recent: Dict[Tuple[int, int, str], float] = {}
DEDUP_WINDOW = 60.0

def _seen(chat_id: int, user_id: int, kind: str) -> bool:
    now = time.time()
    key = (chat_id, user_id, kind)
    last = _recent.get(key, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _recent[key] = now
    # prune
    for k, ts in list(_recent.items()):
        if now - ts > 5 * DEDUP_WINDOW:
            _recent.pop(k, None)
    return False

_store = DMReadyStore()

async def _remove_if_needed(client: Client, chat_id: int, user: User, reason: str):
    if chat_id not in DMREADY_WATCH_IDS or not user or user.is_bot:
        return
    if _seen(chat_id, user.id, "leave"):
        return
    removed = _store.remove_dm_ready_global(user.id)
    if removed:
        # Optional: quiet log to owner? Commented out to keep noise down.
        # owner_id = int(os.getenv("OWNER_ID", "0") or "0")
        # if owner_id:
        #     try:
        #         name = user.first_name or "User"
        #         handle = f" @{user.username}" if user.username else ""
        #         await client.send_message(owner_id, f"ℹ️ DM-ready removed — {name}{handle} (left: {reason})")
        #     except Exception:
        #         pass
        pass

def register(app: Client):

    # Service bubble: left chat member
    @app.on_message(filters.group & filters.left_chat_member)
    async def _on_left_bubble(client: Client, m: Message):
        if not m.left_chat_member:
            return
        await _remove_if_needed(client, m.chat.id, m.left_chat_member, reason="left-bubble")

    # Member updates (covers kicks/bans and also leave when bubbles are off)
    @app.on_chat_member_updated()
    async def _on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return
        if chat.id not in DMREADY_WATCH_IDS:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        # Consider removal whenever final state is "LEFT" or "BANNED"
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            reason = "banned" if new.status == ChatMemberStatus.BANNED else (
                "kicked" if getattr(upd, "from_user", None) and upd.from_user.id != user.id else "left"
            )
            await _remove_if_needed(client, chat.id, user, reason=reason)
