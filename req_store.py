import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

DEFAULT_PATH = os.getenv("REQ_STORE_PATH", "data/req_store.json")
os.makedirs(os.path.dirname(DEFAULT_PATH) or ".", exist_ok=True)

def _month_key(ts: Optional[float] = None) -> str:
    """Return YYYY-MM for the given timestamp."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts or time.time())
    return f"{dt.year:04d}-{dt.month:02d}"

@dataclass
class UserReq:
    purchases: float = 0.0
    games: int = 0
    notes: str = ""
    dm_ready: bool = False

@dataclass
class StoreState:
    # Scoped by month: state["months"][YYYY-MM]["users"][str(user_id)] = UserReq
    months: Dict[str, Dict[str, Dict[str, UserReq]]] = field(default_factory=dict)
    admins: List[int] = field(default_factory=list)

class ReqStore:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.state: StoreState = StoreState()
        self._load()

    # --------------- persistence ---------------
    def _load(self):
        if not os.path.exists(self.path):
            self._save()
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.state = self._from_raw(raw)

    def _save(self):
        raw = self._to_raw(self.state)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

    # --------------- admin mgmt ----------------
    def list_admins(self) -> List[int]:
        return sorted(set(self.state.admins))

    def add_admin(self, user_id: int) -> bool:
        admins = set(self.state.admins)
        if user_id in admins:
            return False
        admins.add(user_id)
        self.state.admins = sorted(admins)
        self._save()
        return True

    def remove_admin(self, user_id: int) -> bool:
        admins = set(self.state.admins)
        if user_id not in admins:
            return False
        admins.remove(user_id)
        self.state.admins = sorted(admins)
        self._save()
        return True

    # --------------- month/user helpers --------
    def _ensure_month(self, key: Optional[str] = None):
        key = key or _month_key()
        self.state.months.setdefault(key, {"users": {}})
        return key

    def _ensure_user(self, user_id: int, month_key: Optional[str] = None) -> Tuple[str, UserReq]:
        mk = self._ensure_month(month_key)
        users = self.state.months[mk]["users"]
        s_uid = str(user_id)
        if s_uid not in users:
            users[s_uid] = asdict(UserReq())
        # hydrate dataclass
        data = users[s_uid]
        if isinstance(data, dict):
            users[s_uid] = data = asdict_to_userreq(data)
        return mk, users[s_uid]

    # --------------- requirement ops -----------
    def add_purchase(self, user_id: int, amount: float, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.purchases += max(0.0, float(amount))
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

    def set_dm_ready(self, user_id: int, ready: bool, month_key: Optional[str] = None):
        mk, u = self._ensure_user(user_id, month_key)
        u.dm_ready = bool(ready)
        self._save()
        return mk, u

    def get_status(self, user_id: int, month_key: Optional[str] = None) -> Tuple[str, UserReq]:
        mk, u = self._ensure_user(user_id, month_key)
        return mk, u

    def export_csv(self, month_key: Optional[str] = None) -> str:
        import csv
        from io import StringIO

        mk = month_key or _month_key()
        self._ensure_month(mk)
        users = self.state.months[mk]["users"]

        sio = StringIO()
        w = csv.writer(sio)
        w.writerow(["user_id", "purchases", "games", "dm_ready", "notes"])
        for s_uid, data in sorted(users.items(), key=lambda x: int(x[0])):
            if isinstance(data, dict):
                data = asdict_to_userreq(data)
            w.writerow([s_uid, f"{data.purchases:.2f}", data.games, int(data.dm_ready), data.notes])
        return sio.getvalue()

    # --------------- raw serde -----------------
    @staticmethod
    def _to_raw(state: StoreState) -> dict:
        months_raw = {}
        for mk, month in state.months.items():
            out_users = {}
            for uid, val in month.get("users", {}).items():
                if isinstance(val, UserReq):
                    out_users[uid] = asdict(val)
                else:
                    out_users[uid] = val
            months_raw[mk] = {"users": out_users}
        return {"months": months_raw, "admins": state.admins}

    @staticmethod
    def _from_raw(raw: dict) -> StoreState:
        months = {}
        for mk, month in raw.get("months", {}).items():
            users = {}
            for uid, val in month.get("users", {}).items():
                users[uid] = asdict_to_userreq(val)
            months[mk] = {"users": users}
        admins = list(map(int, raw.get("admins", [])))
        return StoreState(months=months, admins=admins)

def asdict_to_userreq(d: dict) -> UserReq:
    return UserReq(
        purchases=float(d.get("purchases", 0.0)),
        games=int(d.get("games", 0)),
        notes=str(d.get("notes", "")),
        dm_ready=bool(d.get("dm_ready", False)),
    )
