# utils/dmready_store.py
from __future__ import annotations
import os, json, threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

DATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)
JSON_PATH = os.path.join(DATA_DIR, "dmready.json")

_lock = threading.RLock()

@dataclass
class DMReadyRow:
    user_id: int
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    # ISO-8601 UTC string of the very first time we marked this user DM-ready
    first_marked_iso: str = ""

class DMReadyStore:
    """
    Pure JSON backend; no Mongo.
    File lives at DATA_DIR/dmready.json and is protected by a threading lock.
    """

    def __init__(self, json_path: str = JSON_PATH):
        self.json_path = json_path
        self._rows: Dict[str, DMReadyRow] = {}
        self._load()

    # ---------- private ----------
    def _load(self) -> None:
        with _lock:
            if not os.path.exists(self.json_path):
                self._rows = {}
                return
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._rows = {}
                for k, v in (raw or {}).items():
                    self._rows[k] = DMReadyRow(**v)
            except Exception:
                # corrupted file -> start fresh but don't crash the bot
                self._rows = {}

    def _save(self) -> None:
        with _lock:
            data = {k: asdict(v) for k, v in self._rows.items()}
            tmp = self.json_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.json_path)

    # ---------- public API ----------
    def ensure_dm_ready_first_seen(
        self,
        *,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        when_iso_now_utc: str,
    ) -> str:
        """
        If user_id has never been marked, set first_marked_iso=when_iso_now_utc.
        Return the existing/first timestamp (idempotent).
        """
        key = str(user_id)
        with _lock:
            row = self._rows.get(key)
            if row is None:
                row = DMReadyRow(
                    user_id=user_id,
                    username=username or "",
                    first_name=first_name or "",
                    last_name=last_name or "",
                    first_marked_iso=when_iso_now_utc,
                )
                self._rows[key] = row
                self._save()
                return row.first_marked_iso

            # Already seen: keep the original timestamp, but refresh metadata if missing
            changed = False
            if username and username != row.username:
                row.username = username; changed = True
            if first_name and first_name != row.first_name:
                row.first_name = first_name; changed = True
            if last_name and last_name != row.last_name:
                row.last_name = last_name; changed = True
            if changed:
                self._save()
            return row.first_marked_iso or when_iso_now_utc

    def all(self) -> List[DMReadyRow]:
        with _lock:
            return list(self._rows.values())

    def get(self, user_id: int) -> Optional[DMReadyRow]:
        return self._rows.get(str(user_id))

    def delete(self, user_id: int) -> None:
        with _lock:
            if str(user_id) in self._rows:
                del self._rows[str(user_id)]
                self._save()

# Global singleton used by handlers
global_store = DMReadyStore()

