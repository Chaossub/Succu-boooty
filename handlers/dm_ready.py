# handlers/dm_ready.py
import os
import json
import time
import logging
from typing import Dict, Any, List

from pyrogram import Client, filters
from pyrogram.types import Message, User, ChatMemberUpdated
from pyrogram.enums import ChatType, ChatMemberStatus

log = logging.getLogger("dm_ready")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {
    int(x) for x in (
        os.getenv("SUPER_ADMINS", "").replace(" ", "").split(",")
        if os.getenv("SUPER_ADMINS") else []
    ) if x
}

SANCTUARY_GROUP_ID = int(os.getenv("SANCTUARY_GROUP_ID", "-1002823762054"))

DB_PATH = os.getenv("DMREADY_DB", "data/dm_ready.json")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --------- Tiny JSON store (persistent across restarts) ---------
class _Store:
    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, uid: int) -> Dict[str, Any] | None:
        return self._data.get(str(uid))

    def set(self, uid: int, row: Dict[str, Any]) -> None:
        self._data[str(uid)] = row
        self._save()

    def remove(self, uid: int) -> bool:
        if str(uid) in self._data:
            self._data.pop(str(uid), None)
            self._save()
            return True
        return False

    def all(self) -> List[Dict[str, Any]]:
        return list(self._data.values())

_store = _Store(DB_PATH)

def _is_owner_or_super(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS

# --------- Public helper used by dm_foolproof ---------
async def mark_from_start(client: Client, u: User):
    """Idempotently mark a user DM-ready and ping owner once."""
    if not u or u.is_bot:
        return

    exists = _store.get(u.id)
    if exists:
        return  # already marked; do not spam owner

    now = int(time.time())
    row = {
        "user_id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "username": u.username,
        "when_ts": now,
    }
    _store.set(u.id, row)

    # Notify owner
    if OWNER_ID:
        name = u.first_name or "User"
        handle = f" @{u.username}" if u.username else ""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        try:
            await client.send_message(
                OWNER_ID,
                f"✅ <b>DM-ready:</b> {name}{handle}\n"
                f"<code>{u.id}</code> • {ts}",
                disable_web_page_preview=True
            )
        except Exception as e:
            log.warning("Owner ping failed: %s", e)

def register(app: Client):
    log.info("✅ dm_ready wired (owner=%s, group=%s, db=%s)", OWNER_ID, SANCTUARY_GROUP_ID, DB_PATH)

    # --------- Admin list ----------
    @app.on_message(filters.command("dmreadylist"))
    async def _dmready_list(c: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_owner_or_super(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        rows = sorted(_store.all(), key=lambda r: r.get("when_ts", 0), reverse=True)
        if not rows:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

        lines = ["✅ <b>DM-ready users</b>"]
        for i, r in enumerate(rows, start=1):
            handle = f"@{r.get('username')}" if r.get("username") else ""
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.get("when_ts", 0)))
            lines.append(f"{i}. {r.get('first_name','User')} {handle} — <code>{r['user_id']}</code> • {ts}")

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    # --------- Auto-remove on leave/kick/ban in Sanctuary ----------
    @app.on_chat_member_updated()
    async def _on_member_updated(c: Client, upd: ChatMemberUpdated):
        chat = upd.chat
        if not chat or chat.type == ChatType.PRIVATE or chat.id != SANCTUARY_GROUP_ID:
            return

        user = (upd.new_chat_member.user
                if upd and upd.new_chat_member and upd.new_chat_member.user
                else (upd.old_chat_member.user if upd and upd.old_chat_member else None))
        if not user:
            return

        if upd.new_chat_member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            removed = _store.remove(user.id)
            if removed:
                log.info("🧹 Removed DM-ready for %s (%s) after leaving Sanctuary", user.first_name, user.id)
