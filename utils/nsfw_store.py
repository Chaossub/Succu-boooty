# utils/nsfw_store.py
import os
import json
import tempfile
import threading
from datetime import datetime, timedelta

MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME") or "Succubot"
COLL_AVAIL = os.getenv("NSFW_AVAIL_COLLECTION") or "nsfw_availability"
COLL_BOOK = os.getenv("NSFW_BOOKINGS_COLLECTION") or "nsfw_bookings"

JSON_PATH = os.getenv("NSFW_STORE_PATH", "data/nsfw_text_sessions.json")

_LOCK = threading.RLock()
_USE_MONGO = False
_MC = None
_AV = None
_BK = None

if MONGO_URL:
    try:
        from pymongo import MongoClient
        _MC = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
        _MC.admin.command("ping")
        _AV = _MC[MONGO_DB][COLL_AVAIL]
        _BK = _MC[MONGO_DB][COLL_BOOK]
        _AV.create_index("_id", unique=True)
        _BK.create_index([("yyyymmdd", 1), ("hhmm", 1)], unique=False)
        _USE_MONGO = True
    except Exception:
        _USE_MONGO = False

if not _USE_MONGO:
    os.makedirs(os.path.dirname(JSON_PATH) or ".", exist_ok=True)


def _load_json():
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def _save_json(data: dict):
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="nsfw.", suffix=".json", dir=os.path.dirname(JSON_PATH) or ".")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, JSON_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _ensure_shape(data: dict) -> dict:
    data.setdefault("availability", {})  # yyyymmdd -> {off,start,end,blocks[]}
    data.setdefault("bookings", [])      # list of bookings
    return data


# ---------- Availability ----------

def get_day_config(yyyymmdd: str) -> dict:
    with _LOCK:
        if _USE_MONGO:
            doc = _AV.find_one({"_id": yyyymmdd}) or {}
            return {
                "off": bool(doc.get("off", False)),
                "start": doc.get("start", "") or "",
                "end": doc.get("end", "") or "",
                "blocks": doc.get("blocks", []) or [],
            }

        data = _ensure_shape(_load_json())
        return data["availability"].get(yyyymmdd, {"off": False, "start": "", "end": "", "blocks": []})


def set_day_off(yyyymmdd: str, off: bool) -> None:
    with _LOCK:
        if _USE_MONGO:
            _AV.update_one({"_id": yyyymmdd}, {"$set": {"off": bool(off)}}, upsert=True)
            return
        data = _ensure_shape(_load_json())
        cfg = data["availability"].get(yyyymmdd, {"off": False, "start": "", "end": "", "blocks": []})
        cfg["off"] = bool(off)
        data["availability"][yyyymmdd] = cfg
        _save_json(data)


def set_day_hours(yyyymmdd: str, start: str, end: str) -> None:
    # start/end are "HHMM" or "" to clear
    with _LOCK:
        if _USE_MONGO:
            _AV.update_one(
                {"_id": yyyymmdd},
                {"$set": {"start": start or "", "end": end or "", "off": False}},
                upsert=True,
            )
            return
        data = _ensure_shape(_load_json())
        cfg = data["availability"].get(yyyymmdd, {"off": False, "start": "", "end": "", "blocks": []})
        cfg["start"] = start or ""
        cfg["end"] = end or ""
        if start and end:
            cfg["off"] = False
        data["availability"][yyyymmdd] = cfg
        _save_json(data)


def clear_day_blocks(yyyymmdd: str) -> None:
    with _LOCK:
        if _USE_MONGO:
            _AV.update_one({"_id": yyyymmdd}, {"$set": {"blocks": []}}, upsert=True)
            return
        data = _ensure_shape(_load_json())
        cfg = data["availability"].get(yyyymmdd, {"off": False, "start": "", "end": "", "blocks": []})
        cfg["blocks"] = []
        data["availability"][yyyymmdd] = cfg
        _save_json(data)


def add_day_block(yyyymmdd: str, start: str, end: str) -> None:
    if not (start and end and end > start):
        return
    with _LOCK:
        if _USE_MONGO:
            doc = get_day_config(yyyymmdd)
            blocks = doc.get("blocks", []) or []
            blocks.append({"start": start, "end": end})
            _AV.update_one({"_id": yyyymmdd}, {"$set": {"blocks": blocks}}, upsert=True)
            return
        data = _ensure_shape(_load_json())
        cfg = data["availability"].get(yyyymmdd, {"off": False, "start": "", "end": "", "blocks": []})
        cfg["blocks"] = (cfg.get("blocks") or []) + [{"start": start, "end": end}]
        data["availability"][yyyymmdd] = cfg
        _save_json(data)


# ---------- Booking + availability checks ----------

def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def is_slot_available(yyyymmdd: str, hhmm: str, duration_min: int) -> bool:
    cfg = get_day_config(yyyymmdd)
    if cfg.get("off"):
        return False
    if not cfg.get("start") or not cfg.get("end"):
        return False

    start_dt = datetime.strptime(yyyymmdd + hhmm, "%Y%m%d%H%M")
    end_dt = start_dt + timedelta(minutes=duration_min)

    day_start = datetime.strptime(yyyymmdd + cfg["start"], "%Y%m%d%H%M")
    day_end = datetime.strptime(yyyymmdd + cfg["end"], "%Y%m%d%H%M")
    if not (day_start <= start_dt and end_dt <= day_end):
        return False

    # blocks
    for b in cfg.get("blocks", []) or []:
        b_start = datetime.strptime(yyyymmdd + b["start"], "%Y%m%d%H%M")
        b_end = datetime.strptime(yyyymmdd + b["end"], "%Y%m%d%H%M")
        if _overlaps(start_dt, end_dt, b_start, b_end):
            return False

    # existing bookings
    for bk in list_bookings_for_day(yyyymmdd):
        b_start = datetime.strptime(bk["yyyymmdd"] + bk["hhmm"], "%Y%m%d%H%M")
        b_end = b_start + timedelta(minutes=int(bk["duration_min"]))
        if _overlaps(start_dt, end_dt, b_start, b_end):
            return False

    return True


def list_bookings_for_day(yyyymmdd: str) -> list[dict]:
    with _LOCK:
        if _USE_MONGO:
            return list(_BK.find({"yyyymmdd": yyyymmdd}, {"_id": 0}))
        data = _ensure_shape(_load_json())
        return [b for b in data["bookings"] if b.get("yyyymmdd") == yyyymmdd]


def list_available_slots_for_day(yyyymmdd: str, duration_min: int) -> list[str]:
    cfg = get_day_config(yyyymmdd)
    if cfg.get("off") or not cfg.get("start") or not cfg.get("end"):
        return []

    start = datetime.strptime(yyyymmdd + cfg["start"], "%Y%m%d%H%M")
    end = datetime.strptime(yyyymmdd + cfg["end"], "%Y%m%d%H%M")

    slots = []
    cur = start
    step = timedelta(minutes=30)  # buttons every 30
    while cur + timedelta(minutes=duration_min) <= end:
        hhmm = cur.strftime("%H%M")
        if is_slot_available(yyyymmdd, hhmm, duration_min):
            slots.append(hhmm)
        cur += step

    return slots


def create_booking(user_id: int, username: str, first_name: str, yyyymmdd: str, hhmm: str, duration_min: int, note: str) -> None:
    rec = {
        "user_id": int(user_id),
        "username": username or "",
        "first_name": first_name or "",
        "yyyymmdd": yyyymmdd,
        "hhmm": hhmm,
        "duration_min": int(duration_min),
        "note": note or "",
        "created_at": datetime.utcnow().isoformat(),
        "status": "booked",
    }

    with _LOCK:
        if _USE_MONGO:
            _BK.insert_one(rec)
            return

        data = _ensure_shape(_load_json())
        data["bookings"].append(rec)
        _save_json(data)
