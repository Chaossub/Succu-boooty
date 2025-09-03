# handlers/menu_save_fix.py
# Persistent model menus with Mongo (preferred) + JSON fallback.

import os, json, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

# ---- Mongo (preferred) ----
_MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
_MONGO_DB  = os.getenv("MONGO_DB_NAME", "succubot")
_MONGO_COL = os.getenv("MENUS_COLLECTION", "menus")

_mongo_col = None
if _MONGO_URI:
    try:
        from pymongo import MongoClient
        _cli = MongoClient(_MONGO_URI)
        _db  = _cli[_MONGO_DB]
        _mongo_col = _db[_MONGO_COL]
        _mongo_col.create_index("name_lc", unique=True, name="uniq_name")
        _mongo_col.create_index("updated_at", name="idx_updated")
    except Exception:
        _mongo_col = None

# ---- JSON fallback (works across restarts, may reset on redeploy) ----
JSON_PATH = Path(os.getenv("MENUS_PATH", "data/menus.json"))
JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

@dataclass
class MenuItem:
    name: str
    photo_file_id: str
    caption: str
    updated_at: float

class MenuStore:
    def __init__(self):
        self._cache: Dict[str, MenuItem] = {}
        self._load_json()

    def uses_mongo(self) -> bool:
        return _mongo_col is not None

    # ---------- JSON helpers ----------
    def _load_json(self):
        if JSON_PATH.exists():
            try:
                raw = json.loads(JSON_PATH.read_text())
                self._cache = {k: MenuItem(**v) for k, v in raw.items()}
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _save_json(self):
        JSON_PATH.write_text(json.dumps({k: asdict(v) for k, v in self._cache.items()}, indent=2))

    # ---------- CRUD ----------
    def set_menu(self, name: str, photo_file_id: str, caption: str) -> None:
        now = time.time()
        name_lc = name.strip().lower()
        if _mongo_col is not None:
            try:
                _mongo_col.update_one(
                    {"name_lc": name_lc},
                    {"$set": {
                        "name": name.strip(),
                        "name_lc": name_lc,
                        "photo_file_id": photo_file_id,
                        "caption": caption,
                        "updated_at": now
                    }},
                    upsert=True
                )
                return
            except Exception:
                pass  # fall through to JSON
        self._cache[name_lc] = MenuItem(name=name.strip(), photo_file_id=photo_file_id, caption=caption, updated_at=now)
        self._save_json()

    def update_photo(self, name: str, photo_file_id: str, new_caption: Optional[str] = None) -> bool:
        now = time.time()
        name_lc = name.strip().lower()
        if _mongo_col is not None:
            try:
                doc = _mongo_col.find_one({"name_lc": name_lc})
                if not doc:
                    return False
                upd = {"photo_file_id": photo_file_id, "updated_at": now}
                if new_caption is not None and new_caption.strip():
                    upd["caption"] = new_caption
                _mongo_col.update_one({"name_lc": name_lc}, {"$set": upd})
                return True
            except Exception:
                pass
        item = self._cache.get(name_lc)
        if not item:
            return False
        item.photo_file_id = photo_file_id
        if new_caption is not None and new_caption.strip():
            item.caption = new_caption
        item.updated_at = now
        self._save_json()
        return True

    def update_caption(self, name: str, caption: str) -> bool:
        now = time.time()
        name_lc = name.strip().lower()
        if _mongo_col is not None:
            try:
                res = _mongo_col.update_one({"name_lc": name_lc}, {"$set": {"caption": caption, "updated_at": now}})
                return res.matched_count > 0
            except Exception:
                pass
        item = self._cache.get(name_lc)
        if not item:
            return False
        item.caption = caption
        item.updated_at = now
        self._save_json()
        return True

    def delete_menu(self, name: str) -> bool:
        name_lc = name.strip().lower()
        if _mongo_col is not None:
            try:
                res = _mongo_col.delete_one({"name_lc": name_lc})
                return res.deleted_count > 0
            except Exception:
                pass
        if name_lc in self._cache:
            del self._cache[name_lc]
            self._save_json()
            return True
        return False

    def get_menu(self, name: str) -> Optional[MenuItem]:
        name_lc = name.strip().lower()
        if _mongo_col is not None:
            try:
                d = _mongo_col.find_one({"name_lc": name_lc}, {"_id": 0})
                if not d:
                    return None
                return MenuItem(
                    name=d["name"], photo_file_id=d["photo_file_id"],
                    caption=d.get("caption", ""), updated_at=d.get("updated_at", 0.0)
                )
            except Exception:
                pass
        return self._cache.get(name_lc)

    def list_names(self) -> List[str]:
        if _mongo_col is not None:
            try:
                return [d["name"] for d in _mongo_col.find({}, {"name": 1, "_id": 0}).sort("name_lc", 1)]
            except Exception:
                pass
        return sorted([v.name for v in self._cache.values()], key=str.lower)
