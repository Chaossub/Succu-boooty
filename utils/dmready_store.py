# utils/dmready_store.py
from __future__ import annotations
import os, json, time, threading
from typing import Optional, List, Dict, Tuple

# Mongo optional
_MONGO_ERR = None
try:
    from pymongo import MongoClient, errors as mongo_errors
except Exception as e:  # pragma: no cover
    mongo_errors = None
    MongoClient = None
    _MONGO_ERR = e  # informative only

def _now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

class _MongoStore:
    def __init__(self, uri: str, dbname: str, coll: str = "dm_ready"):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client.get_database(dbname)
        self.col = self.db[coll]
        # ensure unique user_id
        try:
            self.col.create_index("user_id", unique=True)
        except Exception:
            pass

    def mark(self, row: Dict) -> Tuple[bool, Dict]:
        """Upsert that preserves first_seen; returns (created, doc)."""
        user_id = row["user_id"]
        now = _now_iso()
        result = self.col.update_one(
            {"user_id": user_id},
            {
                # preserve first_seen on insert
                "$setOnInsert": {
                    "first_seen": now,
                    "user_id": user_id,
                },
                # but keep fresh profile bits
                "$set": {
                    "first_name": row.get("first_name"),
                    "username": row.get("username"),
                    "last_seen": now,
                }
            },
            upsert=True
        )
        doc = self.col.find_one({"user_id": user_id}) or {}
        created = bool(getattr(result, "upserted_id", None))
        return created, doc

    def all(self) -> List[Dict]:
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
            tmp = {"rows": rows}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(tmp, f, ensure_ascii=False, indent=2)

    def mark(self, row: Dict) -> Tuple[bool, Dict]:
        rows = self._load()
        now = _now_iso()
        for r in rows:
            if r["user_id"] == row["user_id"]:
                # update profile and last_seen only
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
        rows.sort(key=lambda x: x["first_seen"])
        self._save(rows)
        return True, newr

    def all(self) -> List[Dict]:
        return self._load()

    def remove(self, user_id: int) -> bool:
        rows = self._load()
        n2 = [r for r in rows if r["user_id"] != user_id]
        changed = len(n2) != len(rows)
        if changed:
            self._save(n2)
        return changed

    def clear(self) -> None:
        self._save([])

class DMReadyStore:
    """Mongo-backed if possible; JSON fallback."""
    def __init__(self):
        self._mongo: Optional[_MongoStore] = None
        uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or ""
        dbn = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB") or ""
        if uri and dbn and MongoClient is not None:
            try:
                self._mongo = _MongoStore(uri, dbn)
                # quick probe
                _ = self._mongo.all()
            except Exception:
                self._mongo = None  # fallback to JSON
        self._json = _JsonStore(os.getenv("DMREADY_DB", "data/dm_ready.json"))

    # API
    def mark(self, user_id: int, first_name: str, username: Optional[str]) -> Tuple[bool, Dict]:
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

# shared singleton (some handlers import this)
global_store = DMReadyStore()
