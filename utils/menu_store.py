"""
Persistent store for model menus.
- Uses MongoDB when available (recommended for cloud deploys).
- Falls back to an atomic JSON file for local persistence across restarts.

Env (Mongo preferred):
  MONGO_URL or MONGO_URI
  MONGO_DB or MONGO_DB_NAME                  (default: "succubot")
  MONGO_MENU_COLLECTION or MENUS_COLLECTION  (default: "succubot_menus")
JSON fallback:
  MENU_STORE_PATH                            (default: "data/menus.json")
"""
import os, json, tempfile, threading
from typing import Dict, Optional, List

_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
_MONGO_DB  = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or "succubot"
_MENU_COLL = os.getenv("MONGO_MENU_COLLECTION") or os.getenv("MENUS_COLLECTION") or "succubot_menus"
_JSON_PATH = os.getenv("MENU_STORE_PATH", "data/menus.json")

class MenuStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, str] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_MENU_COLL]
                self._use_mongo = True
            except Exception:
                self._use_mongo = False

        if not self._use_mongo:
            os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
            self._load_json()

    # ---------- public ----------
    def set_menu(self, model: str, text: str) -> None:
        model_key = model.strip()
        with self._lock:
            if self._use_mongo:
                self._col.update_one({"_id": model_key}, {"$set": {"text": text}}, upsert=True)
            else:
                self._cache[model_key] = text
                self._save_json()

    def get_menu(self, model: str) -> Optional[str]:
        model_key = model.strip()
        with self._lock:
            if self._use_mongo:
                doc = self._col.find_one({"_id": model_key})
                return doc.get("text") if doc else None
            return self._cache.get(model_key)

    def all_models(self) -> List[str]:
        with self._lock:
            if self._use_mongo:
                return sorted([d["_id"] for d in self._col.find({}, {"_id": 1})])
            return sorted(self._cache.keys())

    # convenience
    def list_names(self) -> List[str]:
        return self.all_models()

    def uses_mongo(self) -> bool:
        return self._use_mongo

    # ---------- json helpers ----------
    def _load_json(self):
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache = {str(k): str(v) for k, v in (data or {}).items()}
        except Exception:
            self._cache = {}

    def _save_json(self):
        tmp_fd, tmp_path = tempfile.mkstemp(prefix="menus.", suffix=".json",
                                            dir=os.path.dirname(_JSON_PATH) or ".")
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

store = MenuStore()
