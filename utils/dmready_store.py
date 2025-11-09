# utils/dmready_store.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from threading import RLock
from typing import Dict, List, Optional
from datetime import datetime, timezone

# Where to keep the persistent file. You can override with DMREADY_JSON in env.
DEFAULT_PATH = os.getenv("DMREADY_JSON", "data/dmready.json")

def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

@dataclass
class DMReadyUser:
    user_id: int
    username: str
    # ISO string, always stored in UTC with "Z"
    first_marked_iso: str

    @staticmethod
    def now_iso() -> str:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class DMReadyStore:
    """
    Thread-safe JSON-backed store. Only the FIRST time a user is marked will be kept.
    """
    def __init__(self, path: str = DEFAULT_PATH):
        self._path = path
        self._lock = RLock()
        self._users: Dict[str, DMReadyUser] = {}
        self._loaded = False
        _ensure_parent_dir(self._path)

    # ---------- low-level ----------
    def _load_unlocked(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.isfile(self._path):
            self._users = {}
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            self._users = {}
            return
        users = {}
        for uid_str, rec in (raw.get("users") or {}).items():
            try:
                users[uid_str] = DMReadyUser(
                    user_id=int(rec.get("user_id", int(uid_str))),
                    username=rec.get("username") or "",
                    first_marked_iso=rec.get("first_marked_iso") or DMReadyUser.now_iso(),
                )
            except Exception:
                continue
        self._users = users

    def _save_unlocked(self) -> None:
        data = {
            "users": {uid: asdict(rec) for uid, rec in self._users.items()}
        }
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)

    # ---------- public API ----------
    def ensure_loaded(self) -> None:
        with self._lock:
            self._load_unlocked()

    def ensure_dm_ready_first_seen(self, user_id: int, username: str, when_iso: Optional[str] = None) -> DMReadyUser:
        """
        Create the record if missing. Never overwrites an existing first_marked_iso.
        Returns the stored record.
        """
        with self._lock:
            self._load_unlocked()
            key = str(user_id)
            if key in self._users:
                # May refresh username if it changed (safe, does not touch the timestamp)
                existing = self._users[key]
                if username and username != existing.username:
                    existing.username = username
                    self._save_unlocked()
                return existing
            rec = DMReadyUser(
                user_id=user_id,
                username=username or "",
                first_marked_iso=(when_iso or DMReadyUser.now_iso()),
            )
            self._users[key] = rec
            self._save_unlocked()
            return rec

    def get(self, user_id: int) -> Optional[DMReadyUser]:
        with self._lock:
            self._load_unlocked()
            return self._users.get(str(user_id))

    def all(self) -> List[DMReadyUser]:
        """Return all users as a list (alias kept for handler compatibility)."""
        with self._lock:
            self._load_unlocked()
            return list(self._users.values())

    # Convenience alias some code prefers
    def all_records(self) -> List[DMReadyUser]:
        return self.all()

# A single global instance you can import
global_store = DMReadyStore()
