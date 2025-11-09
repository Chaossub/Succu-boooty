# utils/dmready_store.py
from __future__ import annotations
import os, json, time, threading
from typing import Dict, List, Any

_DEFAULT_PATH = os.getenv("DMREADY_DB", "data/dm_ready.json")

def _ensure_dir(p: str):
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

class DMReadyStore:
    """
    JSON-backed, restart-safe store for DM-ready users.
    Schema (by user_id as str):
    {
      "6964...": {
        "id": 6964...,
        "first_name": "Roni",
        "username": "Chaossub283",
        "first_marked_iso": "2025-11-08T02:15:35Z"
      },
      ...
    }
    """
    def __init__(self, path: str | None = None):
        self.path = path or _DEFAULT_PATH
        _ensure_dir(self.path)
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------- I/O -------------
    def _load(self) -> None:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        except Exception:
            # Corrupt file: back it up and start fresh
            try:
                os.rename(self.path, self.path + f".corrupt.{int(time.time())}.bak")
            except Exception:
                pass
            self._data = {}

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    # ------------- API -------------
    def mark(self, *, user_id: int, first_name: str = "", username: str | None = None,
             when_iso_utc: str) -> Dict[str, Any]:
        """
        Mark a user DM-ready. If they already exist, do NOT overwrite first_marked_iso.
        Returns the stored record.
        """
        key = str(user_id)
        with self._lock:
            rec = self._data.get(key)
            if rec is None:
                rec = {
                    "id": user_id,
                    "first_name": first_name or "User",
                    "username": username or None,
                    "first_marked_iso": when_iso_utc,  # immutable
                }
                self._data[key] = rec
                self._save()
            else:
                # update display info only (never the timestamp)
                changed = False
                if first_name and rec.get("first_name") != first_name:
                    rec["first_name"] = first_name; changed = True
                if username != rec.get("username"):
                    rec["username"] = username; changed = True
                if changed:
                    self._save()
            return rec

    def remove(self, user_id: int) -> bool:
        key = str(user_id)
        with self._lock:
            if key in self._data:
                self._data.pop(key)
                self._save()
                return True
            return False

    # alias used by some handlers
    def remove_dm_ready_global(self, user_id: int) -> bool:
        return self.remove(user_id)

    def clear(self) -> None:
        with self._lock:
            self._data = {}
            self._save()

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data.values())

# convenient singleton (optional)
global_store = DMReadyStore()
