# req_store.py
import json, os, time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

# ---- Mongo (for DM-ready only) ----
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
        _mongo_col = None  # fallback to JSON

# ---- JSON fallback (ephemeral) ----
DEFAULT_PATH = os.getenv("REQ_STORE_PATH", "data/req_store.json")
os.makedirs(os.path.dirname(DEFAULT_PATH) or ".", exist_ok=True)

def _month_key(ts: float | None = None) -> str:
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
        last_buy_ts=float(obj.get("last_buy_ts", 0)),
        notes=str(obj.get("notes", "")),
    )

class ReqStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.state = StoreState()
        self._load()

    # ---------- persistence introspection ----------
    def uses_mongo(self) -> bool:
        return _mongo_col is not None

    # ---------- load/save ----------
    def _load(self):
        if not os.path.exists(self.path):
            self._save(); return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        months = {}
        for mk, month in (raw.get("months") or {}).items():
            users = {}
            for uid, data in (month.get("users") or {}).items():
                users[uid] = _as_userreq(data) if isinstance(data, dict) else data
            months[mk] = {"users": users}
        self.state = StoreState(
            months=months,
            admins=list(map(int, raw.get("admins", []))),
            dm_ready_global=raw.get("dm_ready_global") or {},
            exemptions=(raw.get("exemptions") or {"global": {}, "groups": {}}),
        )

    def _save(self):
        months_raw = {}
        for mk, month in self.state.months.items():
            out_users = {uid: (asdict(ur) if isinstance(ur, UserReq) else ur)
                         for uid, ur in month.get("users", {}).items()}
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

    # ---------- monthly counters ----------
    def _ensure_user(self, user_id: int, mk: str | None = None) -> Tuple[str, UserReq]:
        key = mk or _month_key()
        if key not in self.state.months:
            self.state.months[key] = {"users": {}}
        users = self.state.months[key]["users"]
        suid = str(user_id)
        if suid not in users:
            users[suid] = UserReq()
        return key, users[suid]

    def add_tokens(self, user_id: int, amount: int, mk: str | None = None):
        mk, u = self._ensure_user(user_id, mk)
        u.tokens += max(0, int(amount)); self._save(); return mk, u

    def add_buy(self, user_id: int, amount: int = 1, mk: str | None = None):
        mk, u = self._ensure_user(user_id, mk)
        u.buys += max(0, int(amount)); u.last_buy_ts = time.time(); self._save(); return
