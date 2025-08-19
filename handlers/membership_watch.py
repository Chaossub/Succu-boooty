# handlers/membership_watch.py
# Clears global DM-ready when a member leaves/kicked/banned (any chat the bot can see).

from contextlib import suppress
from typing import Optional
import os

from pyrogram import Client
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in {OWNER_ID, SUPER_ADMIN_ID})

def register(app: Client):
    @app.on_chat_member_updated()
    async def on_member_change(client: Client, ev: ChatMemberUpdated):
        try:
            uid = ev.new_chat_member.user.id
            if ev.new_chat_member.user.is_bot:
                return
            if _is_admin(uid):
                return
            new_status = ev.new_chat_member.status
            if new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
                if _store:
                    with suppress(Exception):
                        _store.set_dm_ready_global(uid, False)
                return
            with suppress(Exception):
                nm = ev.new_chat_member
                if getattr(nm, "is_member", None) is False:
                    if _store:
                        _store.set_dm_ready_global(uid, False)
        except Exception:
            pass
