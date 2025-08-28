# handlers/welcome.py  (only the relevant bottom part changed)
import os, time, random, contextlib
from typing import Tuple, Dict, Optional
from utils.dmready_store import DMReadyStore
from pyrogram.enums import ChatType, ChatMemberStatus
# ... (rest of your file stays the same)

_store = DMReadyStore()

def register(app: Client):
    # ... your join & service message handlers ...

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        # Joined -> welcome (your existing code)

        # Left / kicked / banned -> clear DM-ready
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            with contextlib.suppress(Exception):
                _store.clear_dm_ready(user.id)
            # send your goodbye (your existing code continues…)
            # ...
