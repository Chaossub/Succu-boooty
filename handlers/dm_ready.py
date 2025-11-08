# handlers/dm_ready.py
import os, json, threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler

GROUP_ID = -1002823762054
OWNER_ID = 6964994611

class DMReadyStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._mongo_ok = False
        self._coll = None
        self._init_mongo()
        self._json_path = os.path.join("data", "dm_ready.json")
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self._json_path):
            with open(self._json_path, "w", encoding="utf-8") as f:
                json.dump({"users": {}}, f)

    def _init_mongo(self):
        uri = os.getenv("MONGO_URI")
        if not uri:
            self._mongo_ok = False
            return
        try:
            from pymongo import MongoClient, ASCENDING
            db_name = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or "chaossunflowerbusiness321"
            self._mongo = MongoClient(uri, serverSelectionTimeoutMS=2000)
            self._db = self._mongo[db_name]
            self._coll = self._db["dm_ready"]
            self._coll.create_index([("user_id", ASCENDING)], unique=True)
            self._db.command("ping")
            self._mongo_ok = True
        except Exception:
            self._mongo_ok = False
            self._coll = None

    def _fallback_to_json(self):
        self._mongo_ok = False
        self._coll = None

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

    def mark_ready(self, user_id: int, first_name: str, username: Optional[str]) -> bool:
        if self._mongo_ok and self._coll is not None:
            try:
                if self._coll.find_one({"user_id": user_id}):
                    return False
                self._coll.insert_one({
                    "user_id": user_id,
                    "first_name": first_name,
                    "username": username,
                    "since": self._now_iso()
                })
                return True
            except Exception:
                self._fallback_to_json()

        data = self._json_load()
        users = data.setdefault("users", {})
        if str(user_id) in users:
            return False
        users[str(user_id)] = {
            "first_name": first_name,
            "username": username,
            "since": self._now_iso()
        }
        self._json_save(data)
        return True

    def remove(self, user_id: int) -> bool:
        if self._mongo_ok and self._coll is not None:
            try:
                res = self._coll.delete_one({"user_id": user_id})
                return bool(res.deleted_count)
            except Exception:
                self._fallback_to_json()

        data = self._json_load()
        users = data.get("users", {})
        if str(user_id) in users:
            users.pop(str(user_id), None)
            data["users"] = users
            self._json_save(data)
            return True
        return False

    def list_all(self) -> List[Dict[str, Any]]:
        if self._mongo_ok and self._coll is not None:
            try:
                return list(self._coll.find({}, {"_id": 0}).sort("since", 1))
            except Exception:
                self._fallback_to_json()

        data = self._json_load()
        out = []
        for k, v in data.get("users", {}).items():
            row = {"user_id": int(k)}
            row.update(v)
            out.append(row)
        out.sort(key=lambda r: r.get("since") or "")
        return out

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        if self._mongo_ok and self._coll is not None:
            try:
                doc = self._coll.find_one({"user_id": user_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception:
                self._fallback_to_json()
        data = self._json_load()
        v = data.get("users", {}).get(str(user_id))
        return {"user_id": user_id, **v} if v else None

store = DMReadyStore()

async def _notify_owner(client: Client, user_id: int, first_name: str, username: Optional[str], since_iso: str):
    tag = f"@{username}" if username else f"{first_name} ({user_id})"
    when = since_iso[:19].replace("T", " ")
    text = (
        "🔔 *New DM-Ready*\n"
        f"• Name: {first_name}\n"
        f"• User: {tag}\n"
        f"• ID: `{user_id}`\n"
        f"• Time: {when} UTC"
    )
    try:
        await client.send_message(OWNER_ID, text, disable_web_page_preview=True)
    except Exception:
        pass

# called by dm_foolproof on /start
async def mark_from_start(client: Client, user) -> bool:
    newly = store.mark_ready(user.id, user.first_name or "", user.username)
    if newly:
        try:
            await client.send_message(user.id, "You’re now DM-ready ✅")
        except Exception:
            pass
        rec = store.get(user.id)
        since_iso = rec.get("since") if rec else datetime.now(timezone.utc).isoformat()
        await _notify_owner(client, user.id, user.first_name or "User", user.username, since_iso)
    return newly

async def on_any_private(client: Client, msg: Message):
    if msg.chat.type == enums.ChatType.PRIVATE and msg.from_user:
        await mark_from_start(client, msg.from_user)

async def on_member_update(client: Client, ev: ChatMemberUpdated):
    st = ev.new_chat_member.status if ev.new_chat_member else None
    if st in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.KICKED):
        if store.remove(ev.new_chat_member.user.id):
            print(f"[DM-READY] Removed {ev.new_chat_member.user.id} (left group)")

async def dmready_list_cmd(client: Client, msg: Message):
    if not msg.from_user or msg.from_user.id != OWNER_ID:
        return
    rows = store.list_all()
    if not rows:
        await msg.reply_text("No one is DM-ready yet.")
        return
    lines = []
    for r in rows[:100]:
        tag = f"@{r['username']}" if r.get("username") else f"{r.get('first_name','User')} ({r['user_id']})"
        when = r.get("since","")[:19].replace("T"," ")
        lines.append(f"• {tag} — since {when} UTC")
    if len(rows) > 100:
        lines.append(f"… and {len(rows) - 100} more.")
    await msg.reply_text(f"**DM-ready users:** {len(rows)}\n" + "\n".join(lines), disable_web_page_preview=True)

def register(app: Client):
    app.add_handler(MessageHandler(on_any_private, filters.private & ~filters.service & ~filters.command(["start"])), group=0)
    app.add_handler(ChatMemberUpdatedHandler(on_member_update, filters.chat(GROUP_ID)), group=0)
    app.add_handler(MessageHandler(dmready_list_cmd, filters.command(["dmreadylist"])), group=0)
