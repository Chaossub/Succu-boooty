# utils/dmready_store.py
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Optional, Dict

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

# ---- Mongo wiring ----
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"

_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]
_col  = _db.get_collection("dm_ready")

# Ensure unique index on user_id once
try:
    _col.create_index([("user_id", ASCENDING)], unique=True, name="uniq_user_id")
except Exception:
    pass

@dataclass
class DMReadyRecord:
    user_id: int
    username: str
    first_marked_iso: str  # UTC ISO string

class DMReadyStore:
    def __init__(self):
        self.col = _col

    def ensure_dm_ready_first_seen(self, *, user_id: int, username: str, when_iso: str) -> DMReadyRecord:
        """
        Idempotently ensure a DM-ready record exists.
        - On first time: inserts { user_id, username, first_marked_iso=when_iso }
        - On subsequent times: updates username (if changed), keeps original first_marked_iso
        Returns the stored record (with the original timestamp).
        """
        # set username always, but timestamp only on insert
        self.col.update_one(
            {"user_id": user_id},
            {
                "$set": {"username": username or ""},
                "$setOnInsert": {"first_marked_iso": when_iso}
            },
            upsert=True
        )
        doc = self.col.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1, "username": 1, "first_marked_iso": 1})
        # Fallback, but should not be needed
        if not doc:
            doc = {"user_id": user_id, "username": username or "", "first_marked_iso": when_iso}
        return DMReadyRecord(
            user_id=int(doc.get("user_id", user_id)),
            username=doc.get("username", "") or "",
            first_marked_iso=doc.get("first_marked_iso", when_iso) or when_iso,
        )

    def all(self) -> List[DMReadyRecord]:
        recs: List[DMReadyRecord] = []
        for d in self.col.find({}, {"_id": 0}).sort("first_marked_iso", ASCENDING):
            recs.append(DMReadyRecord(
                user_id=int(d.get("user_id", 0)),
                username=d.get("username", "") or "",
                first_marked_iso=d.get("first_marked_iso", "") or "",
            ))
        return recs

# singleton
global_store = DMReadyStore()
