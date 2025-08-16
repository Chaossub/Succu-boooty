"""
Disable requirement DMs when a user leaves the Succubus Sanctuary.

.env:
  SUCCUBUS_SANCTUARY=-1001234567890          # comma-separated supported
"""

import os
import logging
from typing import List, Optional

from pyrogram import Client
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

log = logging.getLogger("membership_watch")

# Optional store
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    class _DummyStore:
        def is_dm_ready_global(self, uid: int) -> bool: return False
        def set_dm_ready_global(self, uid: int, ready: bool, by_admin: bool=False): pass
    _store = _DummyStore()

def _parse_id_list(value: str) -> List[int]:
    if not value:
        return []
    parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
    out: List[int] = []
    for p in parts:
        try: out.append(int(p))
        except Exception: pass
    return out

SANCTUARY_IDS: List[int] = _parse_id_list(os.getenv("SUCCUBUS_SANCTUARY", "")) or _parse_id_list(os.getenv("MODELS_CHAT", ""))

def _is_sanctuary(chat_id: int) -> bool:
    return chat_id in SANCTUARY_IDS

def _opted_in(user_id: int, chat_id: Optional[int]) -> bool:
    checker = getattr(_store, "is_req_opted_in", None)
    if callable(checker) and chat_id:
        try: return bool(checker(chat_id, user_id))
        except Exception: pass
    try:
        return bool(_store.is_dm_ready_global(user_id))
    except Exception:
        return True

def _disable_reqs(user_id: int, chat_id: Optional[int]) -> None:
    did_anything = False

    fn = getattr(_store, "set_req_opt_in", None)
    if callable(fn) and chat_id:
        try: fn(chat_id, user_id, False); did_anything = True
        except Exception: pass

    fn = getattr(_store, "set_req_notifications", None)
    if callable(fn):
        try: fn(user_id, False, chat_id=chat_id); did_anything = True
        except Exception: pass

    fn = getattr(_store, "disable_req_for_user", None)
    if callable(fn):
        try: fn(user_id, chat_id=chat_id); did_anything = True
        except Exception: pass

    try:
        _store.set_dm_ready_global(user_id, False, by_admin=True); did_anything = True
    except Exception:
        pass

    if not did_anything:
        log.warning("No store method succeeded when disabling reqs for user %s", user_id)

def register(app: Client):
    if not SANCTUARY_IDS:
        log.warning("membership_watch: SUCCUBUS_SANCTUARY/MODELS_CHAT not set; watcher disabled.")
        return

    @app.on_chat_member_updated()
    async def on_member_change(client: Client, u: ChatMemberUpdated):
        chat = u.chat
        if not chat or not _is_sanctuary(chat.id):
            return

        new = u.new_chat_member
        if not new:
            return

        status = new.status
        if status not in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            return

        user = new.user or (u.old_chat_member.user if u.old_chat_member else None)
        if not user:
            return

        uid = user.id
        if _opted_in(uid, chat.id):
            _disable_reqs(uid, chat.id)
            log.info("Requirement notifications deactivated for user %s after leaving chat %s", uid, chat.id)
