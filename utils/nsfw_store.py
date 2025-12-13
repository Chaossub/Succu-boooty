# utils/nsfw_store.py
import json
import os
import time
from dataclasses import dataclass
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
        return {"availability": {}, "bookings": []}
    try:
        with open(NSFW_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {"availability": {}, "bookings": []}
    except Exception:
        return {"availability": {}, "bookings": []}


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


def get_blocks_for_date(date_yyyymmdd: str) -> List[Tuple[str, str]]:
    """
    Returns list of (start_hhmm, end_hhmm) blocks for that date.
    """
    data = _load()
    blocks = (data.get("availability", {}).get("blocks", {}) or {}).get(date_yyyymmdd, []) or []
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
    avail = data.setdefault("availability", {})
    blocks_map = avail.setdefault("blocks", {})
    blocks_map.pop(date_yyyymmdd, None)
    _save(data)


def is_blocked(date_yyyymmdd: str, start_hhmm: str, end_hhmm: str) -> bool:
    s1 = _hhmm_to_min(start_hhmm)
    e1 = _hhmm_to_min(end_hhmm)
    for s, e in get_blocks_for_date(date_yyyymmdd):
        s2 = _hhmm_to_min(s)
        e2 = _hhmm_to_min(e)
        # overlap
        if s1 < e2 and s2 < e1:
            return True
    return False


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
    # latest by created_ts
    candidates = [b for b in bookings if b.get("user_id") == user_id and b.get("status") in statuses]
    if not candidates:
        return None
    candidates.sort(key=lambda x: float(x.get("created_ts", 0)), reverse=True)
    return candidates[0]
