import json
import os
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.getenv("DATA_DIR", "data")
NSFW_STORE_PATH = os.getenv("NSFW_STORE_PATH", os.path.join(DATA_DIR, "nsfw_store.json"))

TZ = "America/Los_Angeles"

# Business hours (LA) from your screenshot:
# Mon–Fri 9a–10p, Sat 9a–9p, Sun 9a–10p
BUSINESS_HOURS = {
    0: ("09:00", "22:00"),  # Mon
    1: ("09:00", "22:00"),  # Tue
    2: ("09:00", "22:00"),  # Wed
    3: ("09:00", "22:00"),  # Thu
    4: ("09:00", "22:00"),  # Fri
    5: ("09:00", "21:00"),  # Sat
    6: ("09:00", "22:00"),  # Sun
}


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load() -> Dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(NSFW_STORE_PATH):
        return {"availability": {"blocks": {}, "allowed": {}}, "bookings": []}
    try:
        with open(NSFW_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        data.setdefault("availability", {})
        data["availability"].setdefault("blocks", {})
        data["availability"].setdefault("allowed", {})
        data.setdefault("bookings", [])
        return data
    except Exception:
        return {"availability": {"blocks": {}, "allowed": {}}, "bookings": []}


def _save(data: Dict[str, Any]) -> None:
    _ensure_dir()
    tmp = f"{NSFW_STORE_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, NSFW_STORE_PATH)


def _hhmm_to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"


def get_business_hours_for_weekday(weekday: int) -> Tuple[str, str]:
    return BUSINESS_HOURS.get(weekday, ("09:00", "22:00"))


# ────────────── BLOCKS (UNAVAILABLE) ──────────────

def get_blocks_for_date(date_yyyymmdd: str) -> List[Tuple[str, str]]:
    data = _load()
    blocks_map = (data.get("availability", {}).get("blocks", {}) or {})
    blocks = blocks_map.get(date_yyyymmdd, []) or []
    out: List[Tuple[str, str]] = []
    for b in blocks:
        s = b.get("start")
        e = b.get("end")
        if s and e:
            out.append((s, e))
    return out


def set_blocks_for_date(date_yyyymmdd: str, blocks: List[Tuple[str, str]]) -> None:
    data = _load()
    avail = data.setdefault("availability", {})
    blocks_map = avail.setdefault("blocks", {})
    blocks_map[date_yyyymmdd] = [{"start": s, "end": e} for (s, e) in blocks]
    _save(data)


def clear_blocks_for_date(date_yyyymmdd: str) -> None:
    data = _load()
    blocks_map = data.setdefault("availability", {}).setdefault("blocks", {})
    blocks_map.pop(date_yyyymmdd, None)
    _save(data)


def is_blocked(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> bool:
    s1 = _hhmm_to_min(start_hhmm)
    e1 = _hhmm_to_min(end_hhmm)
    for s, e in get_blocks_for_date(date_yyyymmdd):
        s2 = _hhmm_to_min(s)
        e2 = _hhmm_to_min(e)
        if s1 < e2 and s2 < e1:
            return True
    return False


# ────────────── ALLOWED WINDOWS (AVAILABLE OVERRIDES) ──────────────
# If allowed windows exist for a date, booking times MUST fall within them.

def get_allowed_for_date(date_yyyymmdd: str) -> List[Tuple[str, str]]:
    data = _load()
    allowed_map = (data.get("availability", {}).get("allowed", {}) or {})
    allowed = allowed_map.get(date_yyyymmdd, []) or []
    out: List[Tuple[str, str]] = []
    for w in allowed:
        s = w.get("start")
        e = w.get("end")
        if s and e:
            out.append((s, e))
    return out


def set_allowed_for_date(date_yyyymmdd: str, windows: List[Tuple[str, str]]) -> None:
    data = _load()
    allowed_map = data.setdefault("availability", {}).setdefault("allowed", {})
    allowed_map[date_yyyymmdd] = [{"start": s, "end": e} for (s, e) in windows]
    _save(data)


def clear_allowed_for_date(date_yyyymmdd: str) -> None:
    data = _load()
    allowed_map = data.setdefault("availability", {}).setdefault("allowed", {})
    allowed_map.pop(date_yyyymmdd, None)
    _save(data)


def add_allowed_window(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> None:
    windows = get_allowed_for_date(date_yyyymmdd)
    windows.append((start_hhmm, end_hhmm))
    # normalize: sort & merge overlaps
    windows = _merge_windows(windows)
    set_allowed_for_date(date_yyyymmdd, windows)


def _merge_windows(windows: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    if not windows:
        return []
    ints = sorted([( _hhmm_to_min(s), _hhmm_to_min(e)) for s, e in windows], key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    for s, e in ints:
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return [(_min_to_hhmm(s), _min_to_hhmm(e)) for s, e in merged]


def is_within_allowed(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> bool:
    allowed = get_allowed_for_date(date_yyyymmdd)
    if not allowed:
        return True  # no overrides -> allowed by default (business hours will be applied elsewhere)
    s1 = _hhmm_to_min(start_hhmm)
    e1 = _hhmm_to_min(end_hhmm)
    for s, e in allowed:
        s2 = _hhmm_to_min(s)
        e2 = _hhmm_to_min(e)
        # fully contained
        if s1 >= s2 and e1 <= e2:
            return True
    return False


# ────────────── BOOKINGS ──────────────

def add_booking(booking: Dict[str, Any]) -> None:
    data = _load()
    data.setdefault("bookings", []).append(booking)
    _save(data)


def update_booking(booking_id: str, patch: Dict[str, Any]) -> bool:
    data = _load()
    bookings = data.setdefault("bookings", [])
    for b in bookings:
        if b.get("booking_id") == booking_id:
            b.update(patch)
            _save(data)
            return True
    return False


def find_latest_booking_for_user(user_id: int, statuses: List[str]) -> Optional[Dict[str, Any]]:
    data = _load()
    bookings = data.get("bookings", []) or []
    candidates = [b for b in bookings if b.get("user_id") == user_id and b.get("status") in statuses]
    if not candidates:
        return None
    candidates.sort(key=lambda x: float(x.get("created_ts", 0)), reverse=True)
    return candidates[0]
