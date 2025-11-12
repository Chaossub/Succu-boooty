# utils/menu_store.py
"""
Persistent store for model menus.
- Uses MongoDB when available (recommended for cloud deploys).
- Falls back to an atomic JSON file for local persistence across restarts.

Env (Mongo preferred):
  MONGO_URL or MONGO_URI
  MONGO_DB or MONGO_DB_NAME or MONGO_DBNAME      (default: "succubot")
  MONGO_MENU_COLLECTION or MENUS_COLLECTION      (default: "succubot_menus")

JSON fallback:
  MENU_STORE_PATH                                (default: "data/menus.json")
"""
import os, json, tempfile, threading, re
from typing import Dict, Optional, List

_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
_MONGO_DB  = (
    os.getenv("MONGO_DB")
    or os.getenv("MONGO_DB_NAME")
    or os.getenv("MONGO_DBNAME")
    or "succubot"
)
_MENU_COLL = (
    os.getenv("MONGO_MENU_COLLECTION")
    or os.getenv("MENUS_COLLECTION")
    or "succubot_menus"
)
_JSON_PATH = os.getenv("MENU_STORE_PATH", "data/menus.json")

_WS_RE = re.compile(r"\s+", re.UNICODE)

def _canon(name: str) -> str:
    if not name:
        return ""
    s = str(name).replace("\u00A0", " ").strip()
    s = _WS_RE.sub(" ", s)
    return s.casefold()

def _pretty(name: str) -> str:
    if not name:
        return ""
    s = str(name).replace("\u00A0", " ").strip()
    s = _WS_RE.sub(" ", s)
    return s

class MenuStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, Dict[str, str]] = {}  # key -> {"name": display, "text": text}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_MENU_COLL]
                self._col.create_index("name", unique=False)
                self._use_mongo = True
                # helpful boot log line (visible in Render)
                print(f"[MenuStore] Mongo OK db={_MONGO_DB} coll={_MENU_COLL}")
            except Exception as e:
                print(f"[MenuStore] Mongo failed ({e}); using JSON fallback")
                self._use_mongo = False

        if not self._use_mongo:
            os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
            self._load_json()

    def set_menu(self, model: str, text: str) -> None:
        key = _canon(model)
        disp = _pretty(model)
        with self._lock:
            if self._use_mongo:
                self._col.update_one(
                    {"_id": key},
                    {"$set": {"name": disp, "text": str(text)}},
                    upsert=True,
                )
            else:
               
