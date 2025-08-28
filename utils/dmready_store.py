# utils/dmready_store.py
import os, json, time, tempfile, shutil
from typing import Dict, List

_DEFAULT_PATH = os.getenv("DMREADY_DB", "data/dm_ready.json")

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

class DMReadyStore:
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT_PATH
        _ensure_dir(self.path)
        self._db: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._db = json.load(f)
        except FileNotFoundError:
            self._db = {}
        except Exception:
            self._db = {}

    def _save(self):
        _ensure_dir(self.path)
        fd, tmp = tempfile.mkstemp(prefix="dmready_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._db, f, ensure_ascii=False, indent=2)
            shutil.move(tmp, self.path)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    def add(self, user_id: int, first_name: str = "", username: str | None = None) -> bool:
        key = str(user_id)
        if key in self._db:
            return False
        self._db[key] = {
            "id": user_id,
            "first_name": first_name,
            "username": username or "",
            "ts": int(time.time()),
        }
        self._save()
        return True

    def is_ready(self, user_id: int) -> bool:
        return str(user_id) in self._db

    def list_all(self) -> List[Dict]:
        return sorted(self._db.values(), key=lambda r: r.get("ts", 0), reverse=True)

    def remove(self, user_id: int) -> bool:
        key = str(user_id)
        if key in self._db:
            self._db.pop(key, None)
            self._save()
            return True
        return False
