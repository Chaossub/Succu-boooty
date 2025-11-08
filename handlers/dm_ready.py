# handlers/dm_ready.py
import os, json, threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from pyrogram import Client, filters, enums
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler

# ==== CONFIG ====
GROUP_ID = -1002823762054   # your main group
OWNER_ID = 6964994611       # you (super admin for /dmreadylist)


# ---------- Storage (Mongo first, JSON resilient fallback) ----------
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
            self._mongo = MongoClient(uri, serverSelectionTimeoutMS=2000)  # fail fast if cluster is down
            self._db = self._mongo[db_name]
            self._coll = self._db["dm_ready"]
            self._coll.create_index([("user_id", ASCENDING)], unique=True)
            self._db.command("ping")
            self._mongo_ok = True
        except Exception:
            self._mongo_ok = False
            self._coll = None

    def _fallback_to_json(self):
        # switch to JSON mode if Mongo fails at runtime
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

    # ----- public API -----
    def mark_ready(self, user_id: int, first_name: str, username: Optional[str]) -> bool:
        """
        Mark a user as DM-ready.
        Returns True if this is the FIRST time (newly marked), False if already present.
        """
        if self._mongo_ok and self._coll is not None:
            try:
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
            except Exception:
                self._fallback_to_json()

        # JSON fallback path
        data = self._json_load()
        users = data.get("users", {})
        if str(user_id) in users:
            return False
        us
