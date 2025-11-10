# utils/menu_store.py
"""
Persistent store for model menus.
- Uses MongoDB when available (recommended for cloud deploys).
- Falls back to an atomic JSON file for local persistence across restarts.

Env vars (Mongo preferred):
  MONGO_URL or MONGO_URI           -> full Mongo connection string
  MONGO_DB or MONGO_DB_NAME        -> database name (default: "succubot")
  MONGO_MENU_COLLECTION or MENUS_COLLECTION -> collection name (default: "succubot_menus")

JSON fallback:
  MENU_STORE_PATH                  -> path to JSON file (default: "data/menus.json")
"""

import os
import json
import tempfile
import threading
from typing import Dict, Optional, List

# ---- Env compatibility shims ----
_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")  # accept either
_MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or "succubot"
_MENU_COLL = os.getenv("MONGO_MENU_COLLECTION") or os.getenv("MENUS_COLLECTION") or "succubot_menus"
_JSON_PATH = os.getenv("MENU_STORE_PATH", "data/menus.json")


class MenuStore:
    """
    Thread-safe, persistent menu store.
    - If Mongo is reachable, uses it.
    - Otherwise uses an on-disk JSON file with atomic writes.
    Schema:
      Mongo:
        _id: <model name as key>
        text: <menu text>
      JSON:
        { "<model>": "<text>", ... }
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, str] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                # quick sanity ping
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_MENU_COLL]
                self._use_mongo = True
            except Exception:
                # Fall back to JSON if Mongo not reachable
                self._use_mongo = False

        if not self._use_mongo:
            # Ensure path exists and load cache
            os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
            self._load_json()

    # ---------- public API ----------
    def set_menu(self, model: str, text: str) -> None:
        """Create or update a menu for the given model name."""
        model_key = model.strip()
        with self._lock:
            if self._use_mongo:
                self._col.update_one({"_id": model_key}, {"$set": {"text": text}}, upsert=True)
            else:
                self._cache[model_key] = text
                self._save_json()

    def get_menu(self, model: str) -> Optional[str]:
        """Return the menu text for a model, or None if not found."""
        model_key = model.strip()
        with self._lock:
            if self._use_mongo:
                doc = self._col.find_one({"_id": model_key})
                return doc.get("text") if doc else None
            return self._cache.get(model_key)

    def all_models(self) -> List[str]:
        """Return a sorted list of all model names that have menus."""
        with self._lock:
            if self._use_mongo:
                return sorted([d["_id"] for d in self._col.find({}, {"_id": 1})])
            return sorted(self._cache.keys())

    # Convenience aliases used by handlers
    def list_names(self) -> List[str]:
        return self.all_models()

    def uses_mongo(self) -> bool:
        return self._use_mongo

    # ---------- JSON helpers ----------
    def _load_json(self):
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # ensure dict[str,str]
                self._cache = {str(k): str(v) for k, v in (data or {}).items()}
        except Exception:
            self._cache = {}

    def _save_json(self):
        # Atomic write to avoid corruption
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="menus.", suffix=".json", dir=os.path.dirname(_JSON_PATH) or ".")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, _JSON_PATH)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


# Shared singleton used by handlers (createmenu/menu/etc.)
store = MenuStore()
