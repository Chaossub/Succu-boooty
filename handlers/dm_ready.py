# handlers/dm_ready.py — MongoDB-backed DM-ready tracker with robust DB selection
import os
import time
import logging
from typing import Dict, Any, List, Optional

from pyrogram import Client, filters
from pyrogram.types import Message, User, ChatMemberUpdated
from pyrogram.enums import ChatType, ChatMemberStatus

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError, ConfigurationError

log = logging.getLogger("dm_ready")

# ---- Owner / super-admins ----
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
SUPER_ADMINS = {
    int(x) for x in (
        os.getenv("SUPER_ADMINS", "").replace(" ", "").split(",")
        if os.getenv("SUPER_ADMINS") else []
    ) if x
}

def _is_owner_or_super(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS

# ---- Sanctuary group for auto-removal ----
SANCTUARY_GROUP_ID = int(os.getenv("SANCTUARY_GROUP_ID", "-1002823762054"))

# ---- Mongo client / DB / collection ----
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

def _preferred_db_name() -> str:
    return os.getenv("MONGO_DB") or os.getenv("DB_NAME") or "chaossunflowerbusiness321"

client: Optional[MongoClient] = MongoClient(MONGO_URI) if MONGO_URI else None

def _get_db():
    """Choose a database even if the URI has no default DB."""
    if not client:
        return None
    # Try the default db from URI, else fall back to env/default
    try:
        db = client.get_database()
        # PyMongo returns a DB object; if it has no real name, pick our own
        if not getattr(db, "name", None) or db.name in (None, "", "admin"):
            db = client[_preferred_db_name()]
        return db
    except (ConfigurationError, Exception):
        # If get_database() balks due to no default DB in the URI, use env/default
        return client[_preferred_db_name()]

db = _get_db()
col = db["dm_ready"] if db else None
if col:
    try:
        col.create_index([("user_id", ASCENDING)], unique=True, name="uniq_user_id")
        col.create_index([("when_ts", ASCENDING)], name="by_time")
        log.info("✅ dm_ready collection ready (DB=%s, coll=%s)", db.name, col.name)
    except Exception as e:
        log.warning("dm_ready index create failed: %s", e)

# --------- helpers ---------
def _row_for(u: User, when_ts: Optional[int] = None) -> Dict[str, Any]:
    return {
        "user_id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "username": u.username,
        "when_ts": when_ts or int(time.time()),
    }

def _get(u_id: int) -> Optional[Dict[str, Any]]:
    if not col: return None
    return col.find_one({"user_id": u_id})

def _add(row: Dict[str, Any]) -> bool:
    if not col: return False
    try:
        col.insert_one(row)
        return True
    except DuplicateKeyError:
        return False
    except Exception as e:
        log.error("dm_ready insert failed: %s", e)
        return False

def _remove(u_id: int) -> bool:
    if not col: return False
    try:
        res = col.delete_one({"user_id": u_id})
        return res.deleted_count > 0
    except Exception as e:
        log.error("dm_ready remove failed: %s", e)
        return False

def _all() -> List[Dict[str, Any]]:
    if not col: return []
    return list(col.find({}, {"_id": 0}).sort("when_ts", -1))

# --------- public helper used by /start ---------
async def mark_from_start(client: Client, u: User):
    """Idempotently mark a user DM-ready and ping owner once."""
    if not u or u.is_bot or not col:
        return
    if _get(u.id):
        return  # already marked

    row = _row_for(u)
    if _add(row):
        if OWNER_ID:
            name = u.first_name or "User"
            handle = f" @{u.username}" if u.username else ""
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["when_ts"]))
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
    log.info(
        "✅ dm_ready wired (owner=%s, group=%s, mongo=%s)",
        OWNER_ID, SANCTUARY_GROUP_ID, bool(col)
    )

    @app.on_message(filters.command("dmreadylist"))
    async def _dmready_list(c: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_owner_or_super(uid):
            return await m.reply_text("❌ You’re not allowed to use this command.")

        rows = _all()
        if not rows:
            return await m.reply_text("ℹ️ No one is marked DM-ready yet.")

        lines = ["✅ <b>DM-ready users</b>"]
        for i, r in enumerate(rows, start=1):
            handle = f"@{r.get('username')}" if r.get("username") else ""
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r.get("when_ts", 0)))
            lines.append(f"{i}. {r.get('first_name','User')} {handle} — <code>{r['user_id']}</code> • {ts}")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    # Auto-remove when member leaves/kicked/banned from Sanctuary
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
            if _remove(user.id):
                log.info("🧹 Removed DM-ready for %s (%s) after leaving Sanctuary", user.first_name, user.id)
