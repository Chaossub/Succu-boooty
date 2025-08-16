import json
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

# Where to persist requirement data (JSON file)
DEFAULT_PATH = os.getenv("REQ_STORE_PATH", "data/req_store.json")
os.makedirs(os.path.dirname(DEFAULT_PATH) or ".", exist_ok=True)

def _month_key(ts: Optional[float] = None) -> str:
    """Return current month key as YYYY-MM."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts or time.time())
    return f"{dt.year:04d}-{dt.month:02d}"

@dataclass
class UserReq:
    purchases: float = 0.0
    games: int = 0
    notes: str = ""
    # Monthly flag retained for back-compat (not used for global DM-ready logic)
    dm_ready: bool = False

@dataclass
class StoreState:
    # months[YYYY-MM]["users"][str(user_id)] = UserReq
    months: Dict[str, Dict[str, Dict[str, UserReq]]] = field(default_factory=dict)
    admins: List[int] = field(default_factory=list)
    # Global (indefinite) DM-ready users: { user_id_str: {"since": float, "by_admin": bool} }
    dm_ready_global: Dict[str, dict] = field(default_factory=dict)
    # Exemptions for requirement enforcement
    exemptions: Dict[str, dict] = field(default_factory=lambda: {"global": {}, "groups": {}})

def _as_userreq(d: dict) -> UserReq:
    return UserReq(
        purchases=float(d.get("purchases", 0.0)),
        games=int(d.get("games", 0)),
        notes=str(d.get("notes", "")),
        dm_ready=bool(d.get("dm_ready", False)),
    )

class ReqStore:
    """JSON-backed store for monthly requirements, admins, exemptions, and global DM-ready."""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self.state: StoreState = StoreState()
        self._load()

    # ---------- persistence ----------
    def _load(self):
        if not os.path.exists(self.path):
            self._save()
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # months
        months: Dict[str, Dict[str, Dict[str, UserReq]]] = {}
        for mk, month in raw.get("months", {}).items():
            users = {}
            for uid, data in month.get("users", {}).items():
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
            for uid, val in month.get("users", {}).items():
                out_users[uid] = asdict(val) if isinstance(val, UserReq) else val
            months_raw[mk] = {"users": out_users}
        raw = {
            "months": months_raw,
            "admins": self.state.admins,
            "dm_ready_global": self.state.dm_ready_global,
            "exemptions": self.state.exemptions,
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

    # ---------- admins ----------
    def list_admins(self) -> List[int]:
        return sorted(set(self.state.admins))

    def add_admin(self, user_id: int) -> bool:
        s = set(self.state.admins)
        if user_id in s:
            return False
        s.add(user_id)
        self.state.admins = sorted(s)
        self._save()
        return True

    def remove_admin(self, user_id: int) -> bool:
        s = set(self.state.admins)
        if user_id not in s:
            return False
        s.remove(user_id)
        self.state.admins = sorted(s)
        self._save()
        return True

    # ---------- month/user helpers ----------
    def _ensure_month(self, key: Optional[str] = None) -> str:
        key = key or _month_key()
        self.state.months.setdefault(key, {"users": {}})
        return key

    def _ensure_user(self, user_id: int, month_key: Optional[str] = None) -> Tuple[str, UserReq]:
        mk = self._ensure_month(month_key)
        users = self.state.months[mk]["users"]
        s_uid = str(user_id)
        if s_uid not in users:
            users[s_uid] = UserReq()
        elif isinstance(users[s_uid], dict):
            users[s_uid] = _as_userreq(users[s_uid])
        return mk, users[s_uid]

    # ---------- requirement ops ----------
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

    # ---------- GLOBAL DM-READY ----------
    def set_dm_ready_global(self, user_id: int, ready: bool, by_admin: bool = False):
        s_uid = str(user_id)
        if ready:
            self.state.dm_ready_global[s_uid] = {"since": time.time(), "by_admin": bool(by_admin)}
        else:
            self.state.dm_ready_global.pop(s_uid, None)
        self._save()

    def is_dm_ready_global(self, user_id: int) -> bool:
        return str(user_id) in self.state.dm_ready_global

    def list_dm_ready_global(self) -> Dict[str, dict]:
        return dict(self.state.dm_ready_global)

    # ---------- status/export ----------
    def get_status(self, user_id: int, month_key: Optional[str] = None):
        return self._ensure_user(user_id, month_key)

    def export_csv(self, month_key: Optional[str] = None) -> str:
        import csv
        from io import StringIO
        mk = month_key or _month_key()
        self._ensure_month(mk)
        users = self.state.months[mk]["users"]
        sio = StringIO()
        w = csv.writer(sio)
        w.writerow(["user_id", "purchases", "games", "dm_ready", "notes"])
        for s_uid, data in sorted(users.items(), key=lambda kv: int(kv[0])):
            if isinstance(data, dict):
                data = _as_userreq(data)
            w.writerow([s_uid, f"{data.purchases:.2f}", data.games, int(data.dm_ready), data.notes])
        return sio.getvalue()

    # ---------- exemptions ----------
    def _now(self) -> float:
        return time.time()

    def _parse_duration(self, duration: Optional[str]) -> Optional[float]:
        if not duration:
            return None
        s = duration.strip().lower()
        try:
            if s.endswith("h"):
                return float(s[:-1]) * 3600.0
            if s.endswith("d"):
                return float(s[:-1]) * 86400.0
            return float(s) * 3600.0
        except Exception:
            return None

    def add_exemption(self, user_id: int, chat_id: Optional[int] = None, duration: Optional[str] = None, note: str = "") -> dict:
        until = None
        secs = self._parse_duration(duration)
        if secs:
            until = self._now() + secs
        if chat_id is None:
            self.state.exemptions["global"][str(user_id)] = {"until": until, "note": note}
        else:
            gid = str(chat_id)
            groups = self.state.exemptions["groups"]
            groups.setdefault(gid, {})
            groups[gid][str(user_id)] = {"until": until, "note": note}
        self._save()
        return {"until": until, "note": note}

    def remove_exemption(self, user_id: int, chat_id: Optional[int] = None) -> bool:
        removed = False
        if chat_id is None:
            removed = self.state.exemptions["global"].pop(str(user_id), None) is not None
        else:
            gid = str(chat_id)
            grp = self.state.exemptions["groups"].get(gid, {})
            removed = grp.pop(str(user_id), None) is not None
        if removed:
            self._save()
        return removed

    def list_exemptions(self, chat_id: Optional[int] = None) -> Dict[str, dict]:
        if chat_id is None:
            return dict(self.state.exemptions.get("global", {}))
        return dict(self.state.exemptions.get("groups", {}).get(str(chat_id), {}))

    def is_exempt(self, user_id: int, chat_id: Optional[int] = None) -> bool:
        now = self._now()
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

