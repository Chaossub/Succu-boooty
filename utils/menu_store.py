import os, json, tempfile, threading
from typing import Dict, Optional, List

_MONGO_URL = os.getenv("MONGO_URL")  # optional
_MENU_COLL = os.getenv("MONGO_MENU_COLLECTION", "succubot_menus")
_JSON_PATH = os.getenv("MENU_STORE_PATH", "data/menus.json")

class MenuStore:
    """
    Persistent store for model menus.
    - If MONGO_URL is available -> uses MongoDB
    - else -> atomic local JSON file (best-effort across restarts)
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, str] = {}
        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                # try connect once
                self._mc.admin.command("ping")
                db_name = os.getenv("MONGO_DB", "succubot")
                self._col = self._mc[db_name][_MENU_COLL]
                self._use_mongo = True
            except Exception:
                self._use_mongo = False
        if not self._use_mongo:
            # JSON fallback
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
                return doc["text"] if doc and "text" in doc else None
            return self._cache.get(model_key)

    def all_models(self) -> List[str]:
        with self._lock:
            if self._use_mongo:
                return sorted([d["_id"] for d in self._col.find({}, {"_id": 1})])
            return sorted(self._cache.keys())

    # ---------- json helpers ----------
    def _load_json(self):
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def _save_json(self):
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

# singleton
store = MenuStore()

