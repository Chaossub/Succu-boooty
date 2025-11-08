# utils/dmready_store.py
from __future__ import annotations
import os, json, threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import pytz

# Mongo optional
try:
    from pymongo import MongoClient  # type: ignore
except Exception:
    MongoClient = None  # type: ignore

LA_TZ = pytz.timezone("America/Los_Angeles")

def _now_iso_local() -> str:
    """Readable timestamp in America/Los_Angeles."""
    return datetime.now(LA_TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")

class _MongoStore:
    def __init__(self, uri: str, dbname: str, coll: str = "dm_ready"):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        # get_database(dbname) – explicit db (avoids "default database" issues)
        self.db = self.client.get_database(dbname)
        self.col = self.db[coll]
        try:
            self.col.create_index("user_id", unique=True)
        except Exception:
            pass

    def mark(self, row: Dict) -> Tuple[bool, Dict]:
        user_id = row["user_id"]
        now = _now_iso_local()
        result = self.col.update_one(
            {"user_id": user_id},
            {
                # First write wins (keep original time)
                "$setOnInsert": {
                    "user_id": user_id,
                    "first_seen": now,
                },
                # Keep user display info fresh and track last_seen
                "$set": {
                    "first_name": row.get("first_name"),
                    "username": row.get("username"),
                    "last_seen": now,
                },
            },
            upsert=True,
        )
        doc = self.col.find_one({"user_id": user_id}, {"_id": 0}) or {}
        created = bool(getattr(result, "upserted_id", None))
        return created, doc

    def all(self) -> List[Dict]:
        # sort by first_seen ascending
        return list(self.col.find({}, {"_id": 0}).sort([("first_seen", 1)]))

    def remove(self, user_id: int) -> bool:
        res = self.col.delete_one({"user_id": user_id})
        return bool(res.deleted_count)

    def clear(self) -> None:
        self.col.delete_many({})

class _JsonStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"rows": []}, f)

    def _load(self) -> List[Dict]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"rows": []}
            return data.get("rows", [])

    def _save(self, rows: List[Dict]) -> None:
        with self._lock:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)

    def mark(self, row: Dict) -> Tuple[bool, Dict]:
        rows = self._load()
        now = _now_iso_local()
        for r in rows:
            if r["user_id"] == row["user_id"]:
                r["first_name"] = row.get("first_name")
                r["username"] = row.get("username")
                r["last_seen"] = now
                self._save(rows)
                return False, r
        newr = {
            "user_id": row["user_id"],
            "first_name": row.get("first_name"),
            "username": row.get("username"),
            "first_seen": now,
            "last_seen": now,
        }
        rows.append(newr)
        self._save(rows)
        return True, newr

    def all(self) -> List[Dict]:
        return self._load()

    def remove(self, user_id: int) -> bool:
        rows = self._load()
        new_rows = [r for r in rows if r["user_id"] != user_id]
        changed = len(new_rows) != len(rows)
        if changed:
            self._save(new_rows)
        return changed

    def clear(self) -> None:
        self._save([])

class DMReadyStore:
    """Prefers Mongo when configured; falls back to JSON."""
    def __init__(self):
        self._mongo: Optional[_MongoStore] = None
        uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or ""
        dbn = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB") or ""
        if uri and dbn and MongoClient:
            try:
                self._mongo = _MongoStore(uri, dbn)
                _ = self._mongo.all()  # smoke test/selects
            except Exception:
                self._mongo = None
        self._json = _JsonStore(os.getenv("DMREADY_DB", "data/dm_ready.json"))

    def mark(self, user_id: int, first_name: str, username: str | None):
        row = {"user_id": user_id, "first_name": first_name, "username": username}
        if self._mongo:
            try:
                return self._mongo.mark(row)
            except Exception:
                pass
        return self._json.mark(row)

    def all(self) -> List[Dict]:
        if self._mongo:
            try:
                return self._mongo.all()
            except Exception:
                pass
        return self._json.all()

    def remove(self, user_id: int) -> bool:
        if self._mongo:
            try:
                if self._mongo.remove(user_id):
                    return True
            except Exception:
                pass
        return self._json.remove(user_id)

    def clear(self) -> None:
        if self._mongo:
            try:
                self._mongo.clear()
                return
            except Exception:
                pass
        self._json.clear()

global_store = DMReadyStore()
