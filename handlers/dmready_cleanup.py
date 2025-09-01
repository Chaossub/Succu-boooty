# handlers/dmready_cleanup.py
# Remove DM-ready status when a user leaves / is kicked / banned from Sanctuary.
import os, logging
from typing import List
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatType, ChatMemberStatus
from utils.dmready_store import DMReadyStore

log = logging.getLogger("handlers.dmready_cleanup")

_SANCT = os.getenv("SANCTUARY_GROUP_IDS") or os.getenv("SANCTUARY_CHAT_ID") or ""
SANCTUARY_GROUP_IDS: List[int] = []
for part in _SANCT.replace(" ", "").split(","):
    if part:
        try:
            SANCTUARY_GROUP_IDS.append(int(part))
        except ValueError:
            pass

store = DMReadyStore()

def register(app: Client):
    if not SANCTUARY_GROUP_IDS:
        log.warning("dmready_cleanup active, but SANCTUARY_GROUP_IDS not set.")

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return
        if SANCTUARY_GROUP_IDS and chat.id not in SANCTUARY_GROUP_IDS:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        # If user left or was banned, drop their DM-ready flag.
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            if store.is_ready(user.id):
                store.clear(user.id)
                log.info("DM-ready cleared for user %s due to leave/ban in %s", user.id, chat.id)
