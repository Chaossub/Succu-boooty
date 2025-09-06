# dm_foolproof.py
#
# - Persist DM-ready across restarts using MongoDB (MONGO_URL)
# - Show ✅ DM-ready banner ONLY the first time a user hits /start
# - /start then calls handlers.panels.main_menu() to render the single welcome + buttons
# - /dmreadylist shows name, @username, telegram id, since
# - Optional auto-cleanup when user leaves/kicked/banned from SANCTUARY_GROUP_IDS
#
# No other handlers are added/changed.

import os
import time
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

# Only import the renderer (it prints the welcome + buttons exactly once)
from handlers.panels import main_menu

# ---------- ENV ----------
MONGO_URL  = os.getenv("MONGO_URL", "").strip()
MONGO_DB   = os.getenv("MONGO_DB", "succubot").strip()
COLL_NAME  = os.getenv("DM_READY_COLL", "dm_ready").strip()

def _ids_from_env(name: str) -> set[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out

SANCTUARY_GROUP_IDS = _ids_from_env("SANCTUARY_GROUP_IDS")

# ---------- Mongo helpers ----------
_client: Optional[MongoClient] = None
_coll: Optional[Collection] = None

def _get_coll() -> Optional[Collection]:
    """Return the Mongo collection or None if not configured."""
    global _client, _coll
    if _coll is not None:
        return _coll
    if not MONGO_URL:
        return None
    _client = MongoClient(MONGO_URL, connectTimeoutMS=5000, serverSelectionTimeoutMS=5000)
    db = _client[MONGO_DB]
    _coll = db[COLL_NAME]
    try:
        _coll.create_index([("user_id", ASCENDING)], unique=True, background=True)
    except Exception:
        pass
    return _coll

def _already_ready(user_id: int) -> bool:
    coll = _get_coll()
    if coll is None:
        return False
    return coll.find_one({"user_id": user_id}, {"_id": 1}) is not None

def _mark_ready(user_id: int, first_name: str, username: str) -> None:
    coll = _get_coll()
    if coll is None:
        return
    now = int(time.time())
    coll.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "since": now
        }},
        upsert=True
    )

def _remove_ready(user_id: int) -> None:
    coll = _get_coll()
    if coll is None:
        return
    try:
        coll.delete_one({"user_id": user_id})
    except Exception:
        pass

def _iter_ready():
    coll = _get_coll()
    if coll is None:
        return []
    return coll.find({}, {"_id": 0}).sort("since", ASCENDING)

# ---------- Register ----------
def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        """
        - First time ever: mark DM-ready in Mongo & show the green banner
        - Then render the single welcome + buttons via main_menu()
        """
        u = m.from_user
        if not u:
            return

        first_time = not _already_ready(u.id)
        if first_time:
            _mark_ready(u.id, (u.first_name or "Someone").strip(), (u.username or ""))
            handle = f"@{u.username}" if u.username else ""
            await m.reply_text(f"✅ DM-ready — {u.first_name} {handle}".rstrip())

        # IMPORTANT: Do NOT send another welcome card here.
        # handlers.panels.main_menu() already renders the welcome + buttons.
        await main_menu(m)

    @app.on_message(filters.command("dmreadylist", prefixes=["/", "!", "."]))
    async def _dm_list(c: Client, m: Message):
        coll = _get_coll()
        if coll is None:
            return await m.reply_text("⚠️ DM-ready list unavailable (MONGO_URL not configured).")

        rows = list(_iter_ready())
        if not rows:
            return await m.reply_text("📬 DM-ready (all)\n• <i>none yet</i>")

        lines = []
        for r in rows:
            uid = r.get("user_id")
            name = r.get("first_name") or "Someone"
            uname = r.get("username") or ""
            handle = f"@{uname}" if uname else ""
            since = r.get("since", 0)
            lines.append(
                f"• <a href='tg://user?id={uid}'>{name}</a> {handle} — id: <code>{uid}</code> — since <code>{since}</code>"
            )
        await m.reply_text("📬 <b>DM-ready (all)</b>\n" + "\n".join(lines), disable_web_page_preview=True)

    # Optional: clean up when a user leaves/kicked/banned from your sanctuary groups
    if SANCTUARY_GROUP_IDS:
        @app.on_chat_member_updated()
        async def _cleanup(c: Client, upd: ChatMemberUpdated):
            try:
                if upd.chat.id not in SANCTUARY_GROUP_IDS:
                    return
                new = upd.new_chat_member
                if not new or not new.user:
                    return
                if new.status in {"kicked", "left", "banned"}:
                    _remove_ready(new.user.id)
            except Exception:
                pass
