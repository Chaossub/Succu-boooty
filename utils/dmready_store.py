# utils/dmready_store.py
# Persistent JSON store for DM-ready users.

import json, os, time, threading
from typing import Dict, Optional, List

_PATH = os.getenv("DMREADY_JSON_PATH", "data/dmready.json")

class DMReadyStore:
    def __init__(self, path: str = _PATH):
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> Dict[str, dict]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
            except Exception:
                return {}

    def _save(self, data: Dict[str, dict]) -> None:
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def set_dm_ready_global(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None) -> bool:
        key = str(user_id)
        data = self._load()
        new = key not in data
        data[key] = {
            "id": user_id,
            "username": (username or None),
            "first_name": (first_name or None),
            "ts": int(time.time()),
        }
        self._save(data)
        return new

    def unset_dm_ready_global(self, user_id: int) -> bool:
        key = str(user_id)
        data = self._load()
        if key in data:
            data.pop(key, None)
            self._save(data)
            return True
        return False

    def is_dm_ready_global(self, user_id: int) -> bool:
        return str(user_id) in self._load()

    def list_all(self) -> List[dict]:
        return list(self._load().values())
