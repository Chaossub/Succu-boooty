# req_store.py
import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

# ---------- Optional Mongo backend (for DM-ready only) ----------
_MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
_MONGO_DB  = os.getenv("MONGO_DB_NAME", "succubot")
_MONGO_COL = os.getenv("DM_READY_COLLECTION", "dm_ready")

_mongo_col = None
if _MONGO_URI:
    try:
        from pymongo import MongoClient
        _client = MongoClient(_MONGO_URI)
        _db = _client[_MONGO_DB]
        _mongo_col = _db[_MONGO_COL]
        _mongo_col.create_index("user_id", unique=True, name="uniq_user_id")
        _mongo_col.create_index("since", name="idx_since")
    except Exception:
        _mongo_col = None  # will fall back to JSON

# ---------- JSON file store (existing behavior) ----------
DEFAULT_PATH = os.getenv("REQ_STORE_PATH", "data/req_store.json")
os.makedirs(os.path.dirname(DEFAULT_PATH) or ".", exist_ok=True)

def _month_key(ts: Optional[float] = None) -> str:
    """Return current month key as YYYY-MM."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts or time.time())
    return f"{dt.year:04d}-{dt.month:02d}"

@dataclass
class UserReq:
    tokens: int = 0
    buys: int = 0
    games: int = 0
    last_buy_ts: float = 0.0
    notes: str = ""

@dataclass
class StoreState:
    months: Dict[str, Dict[str, Dict[str, UserReq]]] = field(default_factory=dict)
    admins: List[int] = field(default_factory=list)
    dm_ready_global: Dict[str, dict] = field(default_factory=dict)
    exemptions: Dict[str, dict] = field(default_factory=lambda: {"global": {}, "groups": {}})

def _as_userreq(obj) -> UserReq:
    if isinstance(obj, UserReq):
        return obj
    return UserReq(
        tokens=int(obj.get("tokens", 0)),
        buys=int(obj.get("buys", 0)),
        games=int(obj.get("games", 0)),
        last_buy_ts=float(obj.get("last_buy_ts", 0.0)),
        notes=str(obj.get("notes", "")),
    )

class ReqStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.state = StoreState()
        self._load()

    # ---------- low-level load/save ----------
    def _load(self):
        if not os.path.exists(self.path):
            self._save()
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        months: Dict[str, Dict[str, Dict[str, UserReq]]] = {}
        for mk, month in (raw.get("months") or {}).items():
            users = {}
            for uid, data in (month.get("users") or {}).items():
                users[uid] = _as_userreq(data) if isinstance(data, dict) else data
            months[mk] = {"users": users}

        admins = list(map(int, raw.get("admins", [])))
        dmrg = raw.get("dm_ready_global") or {}
        ex_raw = raw.get("exemptions") or {"global": {}, "groups": {}}
        if "global" not in ex_raw: ex_raw["global"] = {}
        if "groups" not in ex_raw: ex_raw["groups"] = {}

        self.state = StoreState(
            months=months,
            admins=admins,
            dm_ready_global=dmrg,
            exemptions=ex_raw,
        )

    def _save(self):
        months_raw = {}
        for mk, month in self.state.months.items():
            out_users = {}
            for uid, ur in month.get("users", {}).items():
                out_users[uid] = asdict(ur) if isinstance(ur, UserReq) else ur
            months_raw[mk] = {"users": out_users}
        raw = {
            "months": months_raw,
            "admins": self.state.admins,
            "dm_ready_global": self.state.dm_ready_global,
            "exemptions": self.state.exemptions,
        }
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)

    # ---------- admin list ----------
    def list_admins(self) -> List[int]:
        return list(self.state.admins)

    def add_admin(self, uid: int) -> bool:
        if uid in self.state.admins:
            return False
        self.state.admins.append(uid)
        self._save()
        return True

    def remove_admin(self, uid: int) -> bool:
        if uid not in self.state.admins:
            return False
        self.state.admins.remove(uid)
        self._save()
        return True

    # ---------- monthly user state ----------
    def _ensure_user(self, user_id: int, month_key: Optional[str] = None) -> Tuple[str, UserReq]:
        mk = month_key or _month_key()
        if mk not in self.state.months:
            self.state.months[mk] = {"users": {}}
        users = self.state.months[mk]["users"]
        suid = str(user_id)
        if suid not in users:
            users[suid] = UserReq()
        return mk, users[suid]

    def add_tokens(self, user_id: int, amount: int, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.tokens += max(0, int(amount))
        self._save()
        return mk, u

    def add_buy(self, user_id: int, amount: int = 1, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.buys += max(0, int(amount))
        u.last_buy_ts = time.time()
        self._save()
        return mk, u

    def add_game(self, user_id: int, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.games += 1
        self._save()
        return mk, u

    def set_note(self, user_id: int, note: str, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.notes = note.strip()
        self._save()
        return mk, u

    # ---------- GLOBAL DM-READY (Mongo-backed) ----------
    def set_dm_ready_global(self, user_id: int, ready: bool, by_admin: bool = False) -> bool:
        """
        Returns True if this call changed the state (i.e., newly set or removed).
        Uses Mongo when available, else JSON map.
        """
        suid = str(user_id)
        if _mongo_col is not None:
            try:
                if ready:
                    # upsert unique by user_id
                    res = _mongo_col.update_one(
                        {"user_id": user_id},
                        {"$setOnInsert": {"since": time.time()},
                         "$set": {"by_admin": bool(by_admin)}},
                        upsert=True
                    )
                    # modified_count==0 and upserted_id is None -> already present
                    return bool(res.upserted_id)
                else:
                    res = _mongo_col.delete_one({"user_id": user_id})
                    return res.deleted_count > 0
            except Exception:
                # fall through to JSON on any DB error
                pass

        # JSON fallback
        before = suid in self.state.dm_ready_global
        if ready:
            self.state.dm_ready_global[suid] = {"since": time.time(), "by_admin": bool(by_admin)}
        else:
            self.state.dm_ready_global.pop(suid, None)
        self._save()
        after = suid in self.state.dm_ready_global
        return before != after

    def is_dm_ready_global(self, user_id: int) -> bool:
        if _mongo_col is not None:
            try:
                return _mongo_col.count_documents({"user_id": user_id}, limit=1) > 0
            except Exception:
                pass
        return str(user_id) in self.state.dm_ready_global

    def list_dm_ready_global(self) -> Dict[str, dict]:
        if _mongo_col is not None:
            try:
                out = {}
                for doc in _mongo_col.find({}, {"_id": 0}).sort("since", -1):
                    out[str(doc.get("user_id"))] = {"since": doc.get("since"), "by_admin": doc.get("by_admin", False)}
                return out
            except Exception:
                pass
        return dict(self.state.dm_ready_global)

    # ---------- status/export ----------
    def get_status(self, user_id: int, month_key: Optional[str] = None):
        return self._ensure_user(user_id, month_key)

    def export_csv(self, month_key: Optional[str] = None) -> str:
        import csv, io
        mk = month_key or _month_key()
        users = self.state.months.get(mk, {}).get("users", {})
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["user_id", "tokens", "buys", "games", "last_buy_ts", "notes"])
        for uid, u in users.items():
            if isinstance(u, UserReq):
                u = asdict(u)
            w.writerow([uid, u.get("tokens", 0), u.get("buys", 0), u.get("games", 0), u.get("last_buy_ts", 0), u.get("notes", "")])
        return buf.getvalue()

    # ---------- exemptions ----------
    def add_exemption(self, user_id: int, chat_id: Optional[int] = None, until_ts: Optional[float] = None):
        now = time.time()
        rec = {"until": until_ts} if until_ts else {}
        if chat_id is None:
            self.state.exemptions.setdefault("global", {})[str(user_id)] = rec
        else:
            self.state.exemptions.setdefault("groups", {}).setdefault(str(chat_id), {})[str(user_id)] = rec
        self._save()

    def remove_exemption(self, user_id: int, chat_id: Optional[int] = None):
        if chat_id is None:
            self.state.exemptions.get("global", {}).pop(str(user_id), None)
        else:
            self.state.exemptions.setdefault("groups", {}).get(str(chat_id), {}).pop(str(user_id), None)
        self._save()

    def has_valid_exemption(self, user_id: int, chat_id: Optional[int] = None) -> bool:
        now = time.time()
        if chat_id is not None:
            rec = self.state.exemptions.get("groups", {}).get(str(chat_id), {}).get(str(user_id))
            if rec:
                until = rec.get("until")
                if until is None or until > now:
                    return True
                self.remove_exemption(user_id, chat_id)
        rec = self.state.exemptions.get("global", {}).get(str(user_id))
        if rec:
            until = rec.get("until")
            if until is None or until > now:
                return True
            self.remove_exemption(user_id, None)
        return False
