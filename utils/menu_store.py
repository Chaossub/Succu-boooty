# utils/menu_store.py
# Simple JSON-backed store for model menus.

import json, os, threading
from typing import Dict, Optional

_DEFAULT_PATH = os.getenv("MENUS_JSON_PATH", "data/menus.json")

class MenuStore:
    def __init__(self, path: str = _DEFAULT_PATH):
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> Dict[str, str]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
            except Exception:
                return {}

    def _save(self, data: Dict[str, str]) -> None:
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def set_menu(self, key: str, text: str) -> None:
        key = key.lower().strip()
        data = self._load()
        data[key] = text.strip()
        self._save(data)

    def get_menu(self, key: str) -> Optional[str]:
        key = key.lower().strip()
        return self._load().get(key)

    def all(self) -> Dict[str, str]:
        return self._load()
