# utils/dmready_store.py
from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict
from threading import RLock
from typing import Dict, List, Optional
from datetime import datetime, timezone

DEFAULT_PATH = os.getenv("DMREADY_JSON", "data/dmready.json")

def _ensure_dir(path: str):
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

@dataclass
class DMReadyUser:
    user_id: int
    username: str
    first_marked_iso: str

    @staticmethod
    def now_iso():
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

class DMReadyStore:
    """Persistent JSON-based DM-ready list with thread-safety."""
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.lock = RLock()
        self.users: Dict[str, DMReadyUser] = {}
        _ensure_dir(self.path)
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            self._save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for uid, rec in (data.get("users") or {}).items():
                self.users[uid] = DMReadyUser(
                    user_id=int(rec["user_id"]),
                    username=rec.get("username", ""),
                    first_marked_iso=rec.get("first_marked_iso", DMReadyUser.now_iso()),
                )
        except Exception:
            self.users = {}

    def _save(self):
        data = {"users": {uid: asdict(u) for uid, u in self.users.items()}}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def ensure_dm_ready_first_seen(self, user_id: int, username: str, when_iso: Optional[str] = None) -> DMReadyUser:
        """Adds user only once, keeps the first timestamp."""
        with self.lock:
            uid = str(user_id)
            if uid in self.users:
                rec = self.users[uid]
                if username and username != rec.username:
                    rec.username = username
                    self._save()
                return rec
            rec = DMReadyUser(
                user_id=user_id,
                username=username or "",
                first_marked_iso=when_iso or DMReadyUser.now_iso(),
            )
            self.users[uid] = rec
            self._save()
            return rec

    def all(self) -> List[DMReadyUser]:
        with self.lock:
            return list(self.users.values())

# Global singleton
global_store = DMReadyStore()

