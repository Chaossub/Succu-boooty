# utils/menu_store.py
"""
Persistent store for model menus.
- Uses MongoDB when available (preferred).
- Falls back to atomic JSON file.

Env (Mongo):
  MONGO_URL or MONGO_URI
  MONGO_DB or MONGO_DB_NAME or MONGO_DBNAME   (default: "Succubot")
  MONGO_MENU_COLLECTION or MENUS_COLLECTION   (default: "succubot_menus")

JSON:
  MENU_STORE_PATH                              (default: "data/menus.json")
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from typing import Dict, List, Optional

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

_WS_RE = re.compile(r"\s+", re.UNICODE)


def _canon(name: str) -> str:
    """Canonical key: trim, collapse ws (incl NBSP), lower."""
    if not name:
        return ""
    s = str(name).replace("\u00A0", " ").strip()
    s = _WS_RE.sub(" ", s)
    return s.casefold()


def _pretty(name: str) -> str:
    """Display form: trim + single spaces, keep case."""
    if not name:
        return ""
    s = str(name).replace("\u00A0", " ").strip()
    return _WS_RE.sub(" ", s)


class MenuStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._use_mongo = False
        # cache shape: key -> {"name": display, "text": text}
        self._cache: Dict[str, Dict[str, str]] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient
                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_MENU_COLL]
                self._col.create_index("name", unique=False)
                self._use_mongo = True
                log.info("MenuStore: Mongo OK db=%s coll=%s", _MONGO_DB, _MENU_COLL)
            except Exception as e:
                log.warning("MenuStore: Mongo unavailable, falling back to JSON: %s", e)
                self._use_mongo = False

        if not self._use_mongo:
            os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
            self._load_json()

    # ---------- public API ----------
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
                self._cache[key] = {"name": disp, "text": str(text)}
                self._save_json()

    def get_menu(self, model: str) -> Optional[str]:
        key = _canon(model)
        disp = _pretty(model)
        with self._lock:
            if self._use_mongo:
                doc = self._col.find_one({"_id": key}, {"text": 1})
                if doc and "text" in doc:
                    return doc["text"]
                # legacy fallback where _id stored mixed-case
                legacy = self._col.find_one({"_id": disp}, {"text": 1})
                if legacy and "text" in legacy:
                    self._col.update_one(
                        {"_id": key},
                        {"$set": {"name": disp, "text": legacy["text"]}},
                        upsert=True,
                    )
                    return legacy["text"]
                return None
            # JSON mode
            rec = self._cache.get(key)
            if rec:
                return rec.get("text")
            # legacy JSON keying by display
            rec = self._cache.get(disp.casefold())
            if rec:
                return rec.get("text")
            return None

    def all_models(self) -> List[str]:
        with self._lock:
            if self._use_mongo:
                out: List[str] = []
                for d in self._col.find({}, {"_id": 1, "name": 1}):
                    out.append(d.get("name") or d.get("_id") or "")
                return sorted({n for n in map(_pretty, out) if n})
            return sorted({rec.get("name") or "" for rec in self._cache.values() if rec.get("name")})

    # convenience
    def list_names(self) -> List[str]:
        return self.all_models()

    def uses_mongo(self) -> bool:
        return self._use_mongo

    # ---------- JSON helpers ----------
    def _load_json(self) -> None:
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            norm: Dict[str, Dict[str, str]] = {}
            for k, v in data.items():
                if isinstance(v, dict) and "text" in v:
                    key = _canon(v.get("name") or k)
                    norm[key] = {"name": _pretty(v.get("name") or k), "text": str(v.get("text", ""))}
                else:
                    key = _canon(k)
                    norm[key] = {"name": _pretty(k), "text": str(v)}
            self._cache = norm
        except Exception:
            self._cache = {}

    def _save_json(self) -> None:
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


# singleton
store = MenuStore()
