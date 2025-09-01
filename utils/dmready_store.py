# utils/dmready_store.py
from __future__ import annotations
import os
import time
from typing import List, Dict, Optional, Tuple

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection


class DMReadyStore:
    """
    Mongo-backed DM-ready registry.
    Collection schema (dm_ready):
      { _id: user_id (int),
        user_id: int,
        username: str | None,
        first_name: str | None,
        created_at: float (epoch),
        updated_at: float (epoch)
      }
    """
    def __init__(self) -> None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set")
        db_name = os.getenv("MONGO_DB", "succubot")
        client = MongoClient(uri)
        db = client[db_name]
        self.col: Collection = db["dm_ready"]
        # Ensure unique on user_id (used as _id too)
        self.col.create_index([("_id", ASCENDING)], unique=True)

    # ── Writes ──────────────────────────────────────────────────────────────────
    def set_ready(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> Tuple[bool, Dict]:
        """
        Upsert user. Returns (is_new, doc).
        """
        now = time.time()
        res = self.col.find_one_and_update(
            {"_id": int(user_id)},
            {"$setOnInsert": {"created_at": now},
             "$set": {
                "user_id": int(user_id),
                "username": username,
                "first_name": first_name,
                "updated_at": now
             }},
            upsert=True,
            return_document=True  # type: ignore[arg-type]
        )
        # find_one_and_update with return_document=True returns the post-update doc,
        # but we still need to know if it existed before:
        is_new = res and abs(res.get("created_at", now) - now) < 1e-6
        # If this heuristic is too tight, explicitly re-check with a prior find.
        return bool(is_new), res or {}

    def clear(self, user_id: int) -> bool:
        d = self.col.delete_one({"_id": int(user_id)})
        return d.deleted_count > 0

    def clear_all(self) -> int:
        d = self.col.delete_many({})
        return d.deleted_count

    # ── Reads ───────────────────────────────────────────────────────────────────
    def is_ready(self, user_id: int) -> bool:
        return self.col.count_documents({"_id": int(user_id)}, limit=1) > 0

    def get_all(self) -> List[Dict]:
        return list(self.col.find({}, sort=[("created_at", ASCENDING)]))

    def count(self) -> int:
        return self.col.estimated_document_count()

