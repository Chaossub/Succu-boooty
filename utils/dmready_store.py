# utils/dmready_store.py
from __future__ import annotations
import json, os, threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

DMREADY_JSON_PATH = os.getenv("DMREADY_JSON_PATH", "data/dm_ready.json")

# ensure folder exists
_os_lock = threading.Lock()
os.makedirs(os.path.dirname(DMREADY_JSON_PATH) or ".", exist_ok=True)

@dataclass
class DMReadyRecord:
    user_id: int
    username: str
    first_marked_iso: str  # UTC ISO string

class DMReadyStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._by_id: Dict[int, DMReadyRecord] = {}
        self._load()

    def _load(self) -> None:
        with _os_lock:
            if not os.path.exists(self.path):
                self._save()  # create empty file
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            data = {}
        self._by_id = {}
        for k, v in data.items():
            try:
                uid = int(k)
                self._by_id[uid] = DMReadyRecord(
                    user_id=uid,
                    username=v.get("username", "") or "",
                    first_marked_iso=v.get("first_marked_iso", "") or "",
                )
            except Exception:
                continue

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({str(k): asdict(v) for k, v in self._by_id.items()}, f, indent=2)

    # ---- API ----
    def ensure_dm_ready_first_seen(self, *, user_id: int, username: str, when_iso: str) -> DMReadyRecord:
        """
        Idempotently mark user as DM-ready the first time.
        Never overwrites the existing first_marked_iso.
        """
        with self._lock:
            rec = self._by_id.get(user_id)
            if rec is None:
                rec = DMReadyRecord(user_id=user_id, username=username or "", first_marked_iso=when_iso)
                self._by_id[user_id] = rec
                self._save()
            else:
                # Update username if it changed (keep original timestamp)
                if (username or "") != rec.username:
                    rec.username = username or ""
                    self._save()
            return rec

    def all(self) -> List[DMReadyRecord]:
        with self._lock:
            return list(self._by_id.values())

# singleton
global_store = DMReadyStore(DMREADY_JSON_PATH)

