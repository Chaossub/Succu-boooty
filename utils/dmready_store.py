# utils/dmready_store.py
import json, os, time, threading
from typing import Dict, List, Optional

class DMReadyStore:
    """
    Very small JSON-backed store:
    {
      "users": { "<user_id>": { "username": "...", "first_name": "...", "ts": 1693000000 } },
      "notified": { "<user_id>": 1693000000 }
    }
    """
    def __init__(self, path: str = "data/dmready.json"):
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._data = {"users": {}, "notified": {}}
        self._load()

    # --------------- internal ---------------
    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {"users": {}, "notified": {}}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # --------------- public API ---------------
    def set_dm_ready_global(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
        """Returns True if it was newly set; False if already present."""
        with self._lock:
            users = self._data.setdefault("users", {})
            if str(user_id) in users:
                return False
            users[str(user_id)] = {
                "username": username or "",
                "first_name": first_name or "",
                "ts": int(time.time())
            }
            self._save()
            return True

    def clear_dm_ready(self, user_id: int) -> None:
        with self._lock:
            self._data.get("users", {}).pop(str(user_id), None)
            self._save()

    def get_all_dm_ready_global(self) -> List[Dict]:
        with self._lock:
            items = []
            for uid, meta in self._data.get("users", {}).items():
                items.append({"user_id": int(uid), **meta})
            items.sort(key=lambda x: x["ts"])
            return items

    # owner notification de-dupe
    def should_notify_owner(self, user_id: int) -> bool:
        with self._lock:
            notified = self._data.setdefault("notified", {})
            key = str(user_id)
            if key in notified:
                return False
            notified[key] = int(time.time())
            self._save()
            return True
