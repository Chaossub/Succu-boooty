# utils/dmready_store.py
import json, os, threading, time
from typing import Dict, List, Optional

_DEFAULT_PATH = os.getenv("DMREADY_STORE_PATH", "data/dmready_store.json")
os.makedirs(os.path.dirname(_DEFAULT_PATH), exist_ok=True)
_lock = threading.Lock()

def _now() -> int:
    return int(time.time())

class DMReadyStore:
    """
    Tiny JSON-backed store:
      key: str(user_id)
      value: { "user_id": int, "username": str|None, "first_name": str|None, "ts": int }
    """
    def __init__(self, path: Optional[str] = None):
        self.path = path or _DEFAULT_PATH
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    # --- private -------------------------------------------------------------
    def _load(self) -> Dict[str, Dict]:
        with _lock:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save(self, data: Dict[str, Dict]) -> None:
        with _lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    # --- public --------------------------------------------------------------
    def mark_ready_once(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
        """
        Returns True if this is the FIRST time we marked this user (i.e. newly DM-ready).
        Returns False if they were already marked.
        """
        data = self._load()
        k = str(user_id)
        if k in data:
            # update cached name/username but keep first_marked ts
            rec = data[k]
            rec["username"] = username or rec.get("username")
            rec["first_name"] = first_name or rec.get("first_name")
            rec["ts_last_seen"] = _now()
            self._save(data)
            return False
        data[k] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "ts": _now(),
            "ts_last_seen": _now(),
        }
        self._save(data)
        return True

    def is_ready(self, user_id: int) -> bool:
        return str(user_id) in self._load()

    def unmark(self, user_id: int) -> None:
        data = self._load()
        data.pop(str(user_id), None)
        self._save(data)

    def get_all(self) -> List[Dict]:
        data = self._load()
        # stable order by first-marked time
        return sorted(data.values(), key=lambda r: r.get("ts", 0))

    def clear_all(self) -> None:
        self._save({})
