# handlers/dm_ready.py
import os, json, threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler

GROUP_ID = -1002823762054  # your main group


# ---------- Storage (Mongo first, JSON fallback) ----------
class DMReadyStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._mongo_ok = False
        self._coll = None
        uri = os.getenv("MONGO_URI")
        if uri:
            try:
                from pymongo import MongoClient, ASCENDING
                self._mongo = MongoClient(uri)
                # if URI has no db, this still works once you call get_database("name")
                db_name = os.getenv("MONGO_DB") or (os.getenv("MONGO_DB_NAME")) or "chaossunflowerbusiness321"
                self._db = self._mongo[db_name]
                self._coll = self._db["dm_ready"]
                self._coll.create_index([("user_id", ASCENDING)], unique=True)
                self._mongo_ok = True
            except Exception:
                self._mongo_ok = False

        self._json_path = os.path.join("data", "dm_ready.json")
        if not self._mongo_ok:
            os.makedirs("data", exist_ok=True)
            if not os.path.exists(self._json_path):
                with open(self._json_path, "w", encoding="utf-8") as f:
                    json.dump({"users": {}}, f)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _json_load(self) -> Dict[str, Any]:
        with self._lock:
            with open(self._json_path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _json_save(self, data: Dict[str, Any]) -> None:
        with self._lock:
            tmp = self._json_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._json_path)

    # ----- public API -----
    def mark_ready(self, user_id: int, first_name: str, username: Optional[str]) -> bool:
        """Returns True if newly marked; False if already present."""
        if self._mongo_ok:
            doc = self._coll.find_one({"user_id": user_id})
            if doc:
                return False
            self._coll.insert_one({
                "user_id": user_id,
                "first_name": first_name,
                "username": username,
                "since": self._now_iso()
            })
            return True
        data = self._json_load()
        users = data.get("users", {})
        if str(user_id) in users:
            return False
        users[str(user_id)] = {
            "first_name": first_name,
            "username": username,
            "since": self._now_iso()
        }
        data["users"] = users
        self._json_save(data)
        return True

    def remove(self, user_id: int) -> bool:
        """Returns True if removed; False if not present."""
        if self._mongo_ok:
            res = self._coll.delete_one({"user_id": user_id})
            return bool(res.deleted_count)
        data = self._json_load()
        users = data.get("users", {})
        if str(user_id) in users:
            users.pop(str(user_id), None)
            data["users"] = users
            self._json_save(data)
            return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        if self._mongo_ok:
            return list(self._coll.find({}, {"_id": 0}).sort("since", 1))
        data = self._json_load()
        users = data.get("users", {})
        out = []
        for k, v in users.items():
            row = {"user_id": int(k)}
            row.update(v)
            out.append(row)
        out.sort(key=lambda r: r.get("since") or "")
        return out


store = DMReadyStore()


# ---------- Handlers ----------
async def dm_first_contact(client: Client, msg: Message):
    """Triggered when someone DMs the bot."""
    user = msg.from_user
    if not user:
        return
    newly_marked = store.mark_ready(
        user_id=user.id,
        first_name=user.first_name or "",
        username=user.username
    )
    if newly_marked:
        try:
            await msg.reply_text("You’re now DM-ready ✅")
        except Exception:
            pass


async def on_member_update(client: Client, event: ChatMemberUpdated):
    """Auto-remove DM-ready users when they leave the group."""
    new = event.new_chat_member
    if not new:
        return
    if new.status in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.KICKED):
        user_id = new.user.id
        removed = store.remove(user_id)
        if removed:
            print(f"[DM-READY] Removed {user_id} (left group)")


async def dmready_list(client: Client, msg: Message):
    """Show list of DM-ready users."""
    rows = store.list_all()
    if not rows:
        await msg.reply_text("No one is DM-ready yet.")
        return
    lines = []
    for r in rows[:100]:
        tag = f"@{r['username']}" if r.get("username") else f"{r.get('first_name','User')} ({r['user_id']})"
        when = r.get("since", "")[:19].replace("T", " ")
        lines.append(f"• {tag} — since {when} UTC")
    extras = ""
    if len(rows) > 100:
        extras = f"\n… and {len(rows) - 100} more."
    await msg.reply_text(
        f"**DM-ready users:** {len(rows)}\n" + "\n".join(lines) + extras,
        disable_web_page_preview=True
    )


# ---------- Register for main.py ----------
def register(app: Client):
    app.add_handler(MessageHandler(dm_first_contact, filters.private & ~filters.service))
    app.add_handler(ChatMemberUpdatedHandler(on_member_update, filters.chat(GROUP_ID)))
    app.add_handler(MessageHandler(dmready_list, filters.command(["dmready", "dmreadylist"]) & filters.chat(GROUP_ID)))
