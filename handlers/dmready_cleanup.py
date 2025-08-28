# handlers/dmready_cleanup.py
# Unset DM-ready when a user leaves / is kicked / banned from Sanctuary group(s).

import os
from typing import Set
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated, User
from pyrogram.enums import ChatMemberStatus, ChatType
from utils.dmready_store import DMReadyStore

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

def _load_groups() -> Set[int]:
    raw = os.getenv("SANCTUARY_GROUP_IDS", "") or ""
    ids = set()
    for tok in raw.replace(",", " ").split():
        tok = tok.strip()
        if tok.lstrip("-").isdigit():
            ids.add(int(tok))
    return ids

SANCTUARY_IDS: Set[int] = _load_groups() or {-1002823762054}
_store = DMReadyStore()

async def _notify_removed(client: Client, u: User, chat_id: int, reason: str):
    if not OWNER_ID:
        return
    try:
        uname = f"@{u.username}" if getattr(u, "username", None) else ""
        mention = f"{u.first_name or 'User'} {uname}".strip()
        await client.send_message(
            OWNER_ID,
            f"⬅️ DM-ready removed — <b>{mention}</b> (<code>{u.id}</code>)\n"
            f"Reason: <b>{reason}</b> in <code>{chat_id}</code>"
        )
    except Exception:
        pass

def register(app: Client):

    @app.on_message(filters.group & filters.left_chat_member)
    async def on_left(client: Client, m: Message):
        if m.chat and SANCTUARY_IDS and m.chat.id not in SANCTUARY_IDS:
            return
        u = m.left_chat_member
        if not u or u.is_bot:
            return
        if _store.unset_dm_ready_global(u.id):
            await _notify_removed(client, u, m.chat.id, "left")

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return
        if SANCTUARY_IDS and chat.id not in SANCTUARY_IDS:
            return

        new = upd.new_chat_member
        old = upd.old_chat_member
        user = (new.user if new and new.user else (old.user if old else None))
        if not user or user.is_bot:
            return

        if new and new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            reason = "banned" if new.status == ChatMemberStatus.BANNED else "left"
            if getattr(upd, "from_user", None) and upd.from_user.id != user.id and new.status != ChatMemberStatus.BANNED:
                reason = "kicked"
            if _store.unset_dm_ready_global(user.id):
                await _notify_removed(client, user, chat.id, reason)
