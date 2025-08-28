# utils/dmready_store.py
import json, os, time
from typing import Dict, List, Optional

_DEFAULT_PATH = os.getenv("DMREADY_PATH", "state/dmready.json")
os.makedirs(os.path.dirname(_DEFAULT_PATH), exist_ok=True)

class DMReadyStore:
    def __init__(self, path: str = _DEFAULT_PATH):
        self.path = path
        self._data: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def set_dm_ready_global(self, user_id: int, username: Optional[str], first: Optional[str]) -> bool:
        key = str(user_id)
        existed = key in self._data
        self._data[key] = {
            "user_id": user_id,
            "username": username or "",
            "first_name": first or "",
            "since": self._data.get(key, {}).get("since") or int(time.time()),
            "updated": int(time.time()),
        }
        self._save()
        return not existed

    def is_dm_ready_global(self, user_id: int) -> bool:
        return str(user_id) in self._data

    def get_all_dm_ready_global(self) -> List[Dict]:
        return sorted(self._data.values(), key=lambda d: d.get("since", 0))

    def remove_dm_ready_global(self, user_id: int) -> bool:
        key = str(user_id)
        if key in self._data:
            self._data.pop(key)
            self._save()
            return True
        return False

    def clear_dm_ready_global(self) -> None:
        self._data = {}
        self._save()
