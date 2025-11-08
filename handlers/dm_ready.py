# handlers/dm_ready.py
# Marks users as DM-ready on /start and stores persistently
from __future__ import annotations
import os
import time
import logging
from typing import Dict, Any

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

from utils.mongo_helpers import get_mongo
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_ready")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
WATCH_GROUP_ID = int(os.getenv("DMREADY_WATCH_GROUP", "-1002823762054") or "-1002823762054")

# Ensure local data dir exists (for JSON fallback persistence)
os.makedirs("data", exist_ok=True)

_mongo_client, _mongo_db = get_mongo()
mongo_ok = _mongo_db is not None
if mongo_ok:
    try:
        _coll = _mongo_db["dm_ready"]
        _coll.create_index("user_id", unique=True)
    except Exception as e:
        log.error("Mongo collection prep failed: %s", e)
        _coll = None
        mongo_ok = False
else:
    _coll = None

_store = DMReadyStore()

def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

def _doc_from_message(m: Message) -> Dict[str, Any]:
    u = m.from_user
    return {
        "user_id": u.id,
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "username": u.username or "",
        "when": _now_iso(),
    }

def _already_marked(user_id: int) -> bool:
    if mongo_ok and _coll is not None:
        try:
            return _coll.find_one({"user_id": user_id}) is not None
        except Exception:
            return _store.exists(user_id)
    return _store.exists(user_id)

def _add_ready(doc: Dict[str, Any]) -> bool:
    if mongo_ok and _coll is not None:
        try:
            _coll.update_one({"user_id": doc["user_id"]}, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            log.warning("Mongo upsert failed: %s", e)
    return _store.add(doc)

async def _notify_owner(app: Client, doc: Dict[str, Any]) -> None:
    if not OWNER_ID:
        return
    handle = f"@{doc['username']}" if doc.get("username") else ""
    txt = (
        f"✅ <b>DM-ready</b>: {doc.get('first_name','User')} {handle}\n"
        f"<code>{doc['user_id']}</code> • {doc['when']}"
    )
    try:
        await app.send_message(OWNER_ID, txt, disable_web_page_preview=True)
    except Exception:
        pass

def register(app: Client):
    log.info("✅ dm_ready wired (owner=%s, group=%s, mongo=%s)",
             OWNER_ID, WATCH_GROUP_ID, mongo_ok)

    @app.on_message(filters.command("start"))
    async def _mark_on_start(client: Client, m: Message):
        # Must be a private DM with the bot
        if not m.from_user or m.chat is None or m.chat.type != ChatType.PRIVATE:
            return

        uid = m.from_user.id
        if _already_marked(uid):
            return

        doc = _doc_from_message(m)
        if _add_ready(doc):
            await _notify_owner(client, doc)

    # expose remover for dmready_cleanup/dmready_watch
    async def _remove(user_id: int) -> bool:
        if mongo_ok and _coll is not None:
            try:
                res = _coll.delete_one({"user_id": user_id})
                if res.deleted_count:
                    return True
            except Exception:
                pass
        return _store.remove(user_id)

    setattr(app, "_succu_dm_store_remove", _remove)
