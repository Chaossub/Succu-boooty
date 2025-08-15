# req_store.py
# Manual requirements tracker (JSON-based, month-scoped)
# Requirement: $20 OR 4+ games. Tracks tip_count, notes, optional display, dm_ready.
# Persistent reminder rotation state. Month archive/clear helpers.

import json, os, csv
from datetime import datetime
from typing import Dict, Any, List, Optional

REQUIREMENT_DOLLARS = 20.0
REQUIREMENT_GAMES = 4
DATA_DIR = os.getenv("REQ_DATA_DIR", "data/requirements")

os.makedirs(DATA_DIR, exist_ok=True)

# --- reminder rotation state (persistent) ---
REM_STATE_PATH = os.path.join(DATA_DIR, "reminder_state.json")

def _load_rem_state():
    if os.path.exists(REM_STATE_PATH):
        try:
            with open(REM_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_idx": -1}

def _save_rem_state(state):
    os.makedirs(os.path.dirname(REM_STATE_PATH), exist_ok=True)
    with open(REM_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def next_reminder_index(n_templates: int) -> int:
    st = _load_rem_state()
    nxt = (int(st.get("last_idx", -1)) + 1) % max(1, n_templates)
    st["last_idx"] = nxt
    _save_rem_state(st)
    return nxt

# --- month docs ---
def month_key(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m")

def month_path(month: Optional[str] = None) -> str:
    m = month or month_key()
    return os.path.join(DATA_DIR, f"requirements_{m}.json")

def _load(month: Optional[str] = None) -> Dict[str, Any]:
    path = month_path(month)
    if not os.path.exists(path):
        return {"month": month or month_key(), "users": {}, "audit": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(doc: Dict[str, Any], month: Optional[str] = None) -> None:
    path = month_path(month or doc.get("month"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

def ensure_month(month: Optional[str] = None) -> Dict[str, Any]:
    doc = _load(month)
    if "month" not in doc: doc["month"] = month or month_key()
    if "users" not in doc: doc["users"] = {}
    if "audit" not in doc: doc["audit"] = []
    return doc

def _user(doc: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    uid = str(user_id)
    if uid not in doc["users"]:
        doc["users"][uid] = {
            "user_id": user_id,
            "tips_usd": 0.0,
            "tip_count": 0,
            "games": 0,
            "met": False,
            "free_pass_until": None,  # "YYYY-MM" or None
            "notes": "",
            "display": "",            # manual display label / @handle
            "dm_ready": False         # for foolproof DM
        }
    return doc["users"][uid]

def _has_active_pass(u: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    if not u.get("free_pass_until"):
        return False
    now = now or datetime.now()
    try:
        y, m = map(int, u["free_pass_until"].split("-"))
        return datetime(y, m, 1) >= datetime(now.year, now.month, 1)
    except Exception:
        return False

def _recompute(u: Dict[str, Any]) -> None:
    u["met"] = (u.get("tips_usd", 0.0) >= REQUIREMENT_DOLLARS) or (u.get("games", 0) >= REQUIREMENT_GAMES)

# --- public API ---

def add_tip(user_id: int, amount: float, month: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["tips_usd"] = round(float(u.get("tips_usd", 0.0)) + float(amount), 2)
    u["tip_count"] = int(u.get("tip_count", 0)) + 1
    _recompute(u)
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "add_tip", "user_id": user_id, "amount": amount, "note": note})
    _save(doc)
    return u

def add_games(user_id: int, count: int, month: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["games"] = max(0, int(u.get("games", 0)) + int(count))
    _recompute(u)
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "add_games", "user_id": user_id, "count": count, "note": note})
    _save(doc)
    return u

def set_pass(user_id: int, until_month: str, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["free_pass_until"] = until_month
    _recompute(u)
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "set_pass", "user_id": user_id, "until": until_month})
    _save(doc)
    return u

def revoke_pass(user_id: int, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["free_pass_until"] = None
    _recompute(u)
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "revoke_pass", "user_id": user_id})
    _save(doc)
    return u

def set_note(user_id: int, text: str, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["notes"] = text
    _recompute(u)
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "set_note", "user_id": user_id, "text": text})
    _save(doc)
    return u

def set_display(user_id: int, display: str, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["display"] = display.strip()
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "set_display", "user_id": user_id, "display": u["display"]})
    _save(doc)
    return u

def remove_user(user_id: int, month: Optional[str] = None) -> bool:
    doc = ensure_month(month)
    uid = str(user_id)
    existed = uid in doc["users"]
    if existed:
        del doc["users"][uid]
        doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "remove_user", "user_id": user_id})
        _save(doc)
    return existed

def status(user_id: int, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    return _user(doc, user_id)

def list_all(month: Optional[str] = None) -> List[Dict[str, Any]]:
    doc = ensure_month(month)
    return list(doc["users"].values())

def list_behind(month: Optional[str] = None) -> List[Dict[str, Any]]:
    doc = ensure_month(month)
    return [u for u in doc["users"].values() if not u.get("met") and not _has_active_pass(u)]

def list_met(month: Optional[str] = None) -> List[Dict[str, Any]]:
    doc = ensure_month(month)
    return [u for u in doc["users"].values() if u.get("met") or _has_active_pass(u)]

def export_csv(path: str, month: Optional[str] = None) -> str:
    doc = ensure_month(month)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "tips_usd", "tip_count", "games", "met", "free_pass_until", "notes", "display", "dm_ready"])
        for u in doc["users"].values():
            w.writerow([
                u["user_id"], u.get("tips_usd",0.0), u.get("tip_count",0), u.get("games",0),
                u.get("met",False), u.get("free_pass_until") or "", u.get("notes",""),
                u.get("display",""), 1 if u.get("dm_ready") else 0
            ])
    return path

def start_month(new_month: Optional[str] = None) -> str:
    m = new_month or month_key()
    doc = {"month": m, "users": {}, "audit": [{"ts": datetime.utcnow().isoformat(), "op": "start_month", "month": m}]}
    _save(doc, m)
    return m

def archive_and_clear(current_month: Optional[str] = None, next_month: Optional[str] = None) -> Dict[str, str]:
    m = current_month or month_key()
    csv_path = os.path.join(DATA_DIR, f"archive_{m}.csv")
    export_csv(csv_path, m)
    created = ""
    if next_month:
        start_month(next_month)
        created = next_month
    return {"archived_csv": csv_path, "next_month_created": created}

def clear_current_month() -> str:
    m = month_key()
    doc = {"month": m, "users": {}, "audit": [{"ts": datetime.utcnow().isoformat(), "op": "clear_month"}]}
    _save(doc, m)
    _save_rem_state({"last_idx": -1})
    return m

# ---- DM readiness tracking ----

def dm_mark_ready(user_id: int, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["dm_ready"] = True
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "dm_mark_ready", "user_id": user_id})
    _save(doc)
    return u

def dm_mark_unready(user_id: int, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    u["dm_ready"] = False
    doc["audit"].append({"ts": datetime.utcnow().isoformat(), "op": "dm_mark_unready", "user_id": user_id})
    _save(doc)
    return u

def dm_is_ready(user_id: int, month: Optional[str] = None) -> bool:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    return bool(u.get("dm_ready", False))

def list_dm_not_ready(month: Optional[str] = None) -> List[Dict[str, Any]]:
    doc = ensure_month(month)
    return [u for u in doc["users"].values() if not u.get("dm_ready", False)]

# ---- Ensure users (used by /trackall and join-tracking) ----

def ensure_user(user_id: int, month: Optional[str] = None) -> Dict[str, Any]:
    doc = ensure_month(month)
    u = _user(doc, user_id)
    _save(doc)
    return u

def bulk_ensure_users(user_ids: List[int], month: Optional[str] = None) -> Dict[str, int]:
    doc = ensure_month(month)
    added, skipped = 0, 0
    for uid in user_ids:
        key = str(uid)
        if key in doc["users"]:
            skipped += 1
            continue
        _user(doc, uid)
        added += 1
    if added:
        _save(doc)
    return {"added": added, "skipped": skipped}
