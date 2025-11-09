# utils/dmready_store.py
import json
import os
import threading

DB_PATH = os.getenv("DMREADY_DB", "data/dmready.json")


class DMReadyStore:
    """Simple JSON-backed store for DM-ready users with first-seen timestamps."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.lock = threading.RLock()
        self.data = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self.data = {}
            self._save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # ───────────────────────────────────────────────────────────
    # Core DM-ready persistence logic
    # ───────────────────────────────────────────────────────────
    def ensure_dm_ready_first_seen(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        source: str,
        when_iso: str,
    ) -> str:
        """
        Adds a DM-ready record if user not yet present.
        Returns the existing or newly-set first_seen timestamp.
        """
        with self.lock:
            record = self.data.get(str(user_id))
            if record:
                return record.get("first_seen", when_iso)
            self.data[str(user_id)] = {
                "username": username,
                "first_name": first_name,
                "source": source,
                "first_seen": when_iso,
            }
            self._save()
            return when_iso

    def get_all(self):
        with self.lock:
            return dict(self.data)


# Global singleton
global_store = DMReadyStore()
