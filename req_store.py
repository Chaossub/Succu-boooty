import json
import os
from datetime import datetime, timedelta

STORE_FILE = "req_store.json"

if not os.path.exists(STORE_FILE):
    with open(STORE_FILE, "w") as f:
        json.dump({"monthly": {}, "global_dm_ready": {}, "exemptions": {}}, f)

def _load():
    with open(STORE_FILE, "r") as f:
        return json.load(f)

def _save(data):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _month_key():
    now = datetime.utcnow()
    return f"{now.year}-{now.month:02d}"

# Monthly requirements
def get_month_data():
    data = _load()
    mkey = _month_key()
    return data["monthly"].setdefault(mkey, {})

def save_month_data(month_data):
    data = _load()
    mkey = _month_key()
    data["monthly"][mkey] = month_data
    _save(data)

# Global DM-ready
def set_dm_ready(user_id: int, ready: bool):
    data = _load()
    if ready:
        data["global_dm_ready"][str(user_id)] = True
    else:
        data["global_dm_ready"].pop(str(user_id), None)
    _save(data)

def is_dm_ready(user_id: int) -> bool:
    return str(user_id) in _load()["global_dm_ready"]

def list_dm_ready():
    return list(map(int, _load()["global_dm_ready"].keys()))

# Exemptions
def add_exemption(user_id: int, days: int = None, note: str = None):
    data = _load()
    expiry = None
    if days:
        expiry = (datetime.utcnow() + timedelta(days=days)).isoformat()
    data["exemptions"][str(user_id)] = {"expiry": expiry, "note": note}
    _save(data)

def remove_exemption(user_id: int):
    data = _load()
    data["exemptions"].pop(str(user_id), None)
    _save(data)

def get_exemptions():
    data = _load()
    now = datetime.utcnow()
    valid = {}
    for uid, info in list(data["exemptions"].items()):
        if info["expiry"] and datetime.fromisoformat(info["expiry"]) < now:
            data["exemptions"].pop(uid)
        else:
            valid[uid] = info
    _save(data)
    return valid
