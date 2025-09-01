# handlers/dmready_cleanup.py
# Removes DM-ready when a user leaves / is kicked / is banned in Sanctuary.

import os, logging
from pyrogram import Client
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatType, ChatMemberStatus

log = logging.getLogger("dmready_cleanup")

_SANCT = os.getenv("SANCTUARY_GROUP_IDS", "").replace(",", " ").split()
SANCTUARY_GROUP_IDS = [int(x) for x in _SANCT if x.strip()]

def register(app: Client):
    if not SANCTUARY_GROUP_IDS:
        log.warning("No SANCTUARY_GROUP_IDS set; dmready_cleanup will be idle.")
        return

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return
        if chat.id not in SANCTUARY_GROUP_IDS:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            # Use helper exposed by dm_foolproof
            remover = getattr(app, "_succu_dm_store_remove", None)
            if callable(remover):
                await remover(user.id)
            else:
                log.warning("dm_foolproof helper not found; cannot remove DM-ready.")
