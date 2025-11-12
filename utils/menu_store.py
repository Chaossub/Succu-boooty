# utils/menu_store.py
import os
import json
import tempfile
import threading
from typing import Dict, Optional, List
import logging

log = logging.getLogger(__name__)

_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
_MONGO_DB = (
    os.getenv("MONGO_DB")
    or os.getenv("MONGO_DB_NAME")
    or os.getenv("MONGO_DBNAME")
    or "Succubot"
)
_MENU_COLL = (
    os.getenv("MONGO_MENU_COLLECTION")
    or os.getenv("MENUS_COLLECTION")
    or "succubot_menus"
)

_JSON_PATH = os.getenv("MENU_STORE_PATH", "data/menus.json")


class MenuStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, str] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=5000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_MENU_COLL]
                self._use_mongo = True
                log.info("MenuStore: Mongo OK")
            except Exception as e:
                log.warning("MenuStore Mongo FAILED: %s", e)
                self._use_mongo = False

        if not self._use_mongo:
            os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
            self._load_json()
            log.info("MenuStore: using JSON file")

    def set_menu(self, model: str, text: str) -> None:
        key = model.strip()
        if not key:
            return
        with self._lock:
            if self._use_mongo:
                self._col.update_one({"_id": key}, {"$set": {"text": text}}, upsert=True)
            else:
                self._cache[key] = text
                self._save_json()

    def get_menu(self, model: str) -> Optional[str]:
        key = model.strip()
        if not key:
            return None
        with self._lock:
            if self._use_mongo:
                doc = self._col.find_one({"_id": key})
                return doc.get("text") if doc else None
            return self._cache.get(key)

    def all_models(self) -> List[str]:
        with self._lock:
            if self._use_mongo:
                return sorted([d["_id"] for d in self._col.find({}, {"_id": 1})])
            return sorted(self._cache.keys())

    def uses_mongo(self) -> bool:
        return self._use_mongo

    def _load_json(self) -> None:
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_json(self) -> None:
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="menus.", suffix=".json")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)
        os.replace(tmp_path, _JSON_PATH)


store = MenuStore()
