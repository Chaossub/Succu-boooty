# utils/dmready_store.py
# Optional reusable store wrapper (not strictly required by the above).
import os, json, time
from typing import Dict, Any, List

DB_PATH = os.getenv("DMREADY_DB", "data/dm_ready.json")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

class DMReadyStore:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._data: Dict[str, Dict[str, Any]] = {}
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

    def add(self, user_id: int, first_name: str = "", username: str | None = None):
        self._data[str(user_id)] = {
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "when_ts": int(time.time()),
        }
        self._save()

    def remove(self, user_id: int) -> bool:
        if str(user_id) in self._data:
            self._data.pop(str(user_id), None)
            self._save()
            return True
        return False

    def get(self, user_id: int) -> Dict[str, Any] | None:
        return self._data.get(str(user_id))

    def all(self) -> List[Dict[str, Any]]:
        return list(self._data.values())

global_store = DMReadyStore()
