# handlers/welcome.py  (only showing the imports + the on_member_updated change)
import os
# ... your existing imports ...
from utils.dmready_store import DMReadyStore

SANCTUARY_GROUP_IDS = set(
    int(x.strip()) for x in os.getenv("SANCTUARY_GROUP_IDS", "").split(",") if x.strip()
)
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

_store = DMReadyStore()

def register(app: Client):
    # ... your existing on_message handlers remain unchanged ...

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE:
            return

        old = upd.old_chat_member
        new = upd.new_chat_member
        user = (new.user or (old.user if old else None))
        if not user:
            return

        # Joined/approved → MEMBER (your existing welcome logic)
        if new.status == ChatMemberStatus.MEMBER and (not old or old.status != ChatMemberStatus.MEMBER):
            if chat.id in SANCTUARY_GROUP_IDS:
                # Nothing to do here for DM-ready (we mark that on /start)
                pass
            # keep your existing welcome message call:
            if not _seen(chat.id, user.id, "join"):
                await _send_welcome(client, chat.id, user)
            return

        # Left / kicked / banned → drop their DM-ready flag if they were marked
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            # Only enforce for configured sanctuary groups
            if chat.id in SANCTUARY_GROUP_IDS:
                removed = _store.clear(user.id)
                if removed and OWNER_ID:
                    with contextlib.suppress(Exception):
                        action = "banned" if new.status == ChatMemberStatus.BANNED else "left/kicked"
                        uname = f"@{user.username}" if user.username else "(no username)"
                        await client.send_message(
                            OWNER_ID,
                            f"🗑️ Removed DM-ready — {user.first_name or 'User'} {uname} ({action})"
                        )

            # keep your existing goodbye text
            if _seen(chat.id, user.id, "leave"):
                return
            reason = "banned" if new.status == ChatMemberStatus.BANNED else (
                "kicked" if getattr(upd, "from_user", None) and upd.from_user.id != user.id else "left"
            )
            await _send_goodbye(client, chat.id, user, reason=reason)
            return
