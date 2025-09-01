# utils/dmready_store.py
# Tiny JSON-backed store that survives restarts.

import os, json, time, threading
from typing import Dict, Any, List

_DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(_DATA_DIR, exist_ok=True)
_PATH = os.path.join(_DATA_DIR, "dm_ready.json")
_LOCK = threading.RLock()

class DMReadyStore:
    def __init__(self, path: str = _PATH):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"users": {}, "recent_mark": {}}, f)

    def _load(self) -> Dict[str, Any]:
        with _LOCK:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"users": {}, "recent_mark": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        with _LOCK:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def is_ready(self, user_id: int) -> bool:
        data = self._load()
        return str(user_id) in data.get("users", {})

    def set_ready(self, user_id: int, username: str = None, first_name: str = None) -> None:
        data = self._load()
        data.setdefault("users", {})[str(user_id)] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "ts": int(time.time()),
        }
        data.setdefault("recent_mark", {})[str(user_id)] = int(time.time())
        self._save(data)

    def clear(self, user_id: int) -> None:
        data = self._load()
        data.get("users", {}).pop(str(user_id), None)
        self._save(data)

    def all(self) -> List[Dict[str, Any]]:
        data = self._load()
        return list(data.get("users", {}).values())

    def was_just_marked(self, user_id: int, window_sec: int = 300) -> bool:
        """True only once right after set_ready (used to notify owner a single time)."""
        data = self._load()
        ts = data.get("recent_mark", {}).pop(str(user_id), None)
        if ts is not None:
            self._save(data)
            # within 5 minutes counts as "just"
            return (int(time.time()) - int(ts)) <= window_sec
        return False

