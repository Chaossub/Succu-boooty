# handlers/dm_ready.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.types import Message

# -------- time utils (LA) ----------
try:
    import pytz
    LA_TZ = pytz.timezone("America/Los_Angeles")
except Exception:
    LA_TZ = None  # fallback without pytz

def _iso_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _iso_to_la_str(iso: str) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if LA_TZ:
            dt = dt.astimezone(LA_TZ)
        else:
            # naive fallback: show UTC with suffix
            return dt.strftime("%Y-%m-%d %I:%M %p") + " UTC"
        return dt.strftime("%Y-%m-%d %I:%M %p PT")
    except Exception:
        return iso

# -------- persistence layer ----------
class DMReadyStore:
    """
    Mongo if MONGO_URL* is present; otherwise JSON file at data/dmready.json.
    API:
      - ensure_dm_ready_first_seen(user_id, username, first_name, last_name, when_iso_now_utc) -> str(created_at_iso)
      - get_first_mark_iso(user_id) -> Optional[str]
      - all() -> List[Dict]
    """
    def __init__(self):
        self.mode = "json"
        self._col = None

        mongo_url = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
        if mongo_url:
            try:
                from pymongo import MongoClient, ASCENDING
                db_name = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
                cli = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
                db = cli[db_name]
                self._col = db.get_collection("dm_ready_users")
                # ensure useful index (unique by user_id ensures idempotency)
                self._col.create_index("user_id", unique=True)
                self.mode = "mongo"
            except Exception:
                self.mode = "json"
                self._col = None

        # JSON fallback
        self._path = Path("data/dmready.json")
        if self.mode == "json":
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._path.write_text("{}", encoding="utf-8")

    # ------ JSON helpers ------
    def _jload(self) -> Dict[str, Dict]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _jdump(self, data: Dict[str, Dict]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    # ------ Public API ------
    def ensure_dm_ready_first_seen(
        self,
        user_id: int,
        username: str,
        first_name: str,
        last_name: str,
        when_iso_now_utc: str,
    ) -> str:
        """Create on first seen, do nothing on repeats. Returns the first_seen ISO string."""
        if self.mode == "mongo":
            from pymongo import ReturnDocument
            # upsert without changing first_seen after it exists
            existing = self._col.find_one({"user_id": user_id})
            if existing:
                return existing.get("first_marked_iso", "")
            doc = {
                "user_id": user_id,
                "username": username or "",
                "first_name": first_name or "",
                "last_name": last_name or "",
                "first_marked_iso": when_iso_now_utc,
            }
            try:
                self._col.insert_one(doc)
            except Exception:
                pass
            return when_iso_now_utc

        # JSON mode
        data = self._jload()
        key = str(user_id)
        if key in data:
            return data[key].get("first_marked_iso", "")
        data[key] = {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
            "first_marked_iso": when_iso_now_utc,
        }
        self._jdump(data)
        return when_iso_now_utc

    def get_first_mark_iso(self, user_id: int) -> Optional[str]:
        if self.mode == "mongo":
            rec = self._col.find_one({"user_id": user_id}) or {}
            return rec.get("first_marked_iso")
        data = self._jload()
        rec = data.get(str(user_id)) or {}
        return rec.get("first_marked_iso")

    def all(self) -> List[Dict]:
        if self.mode == "mongo":
            return list(self._col.find({}, {"_id": 0}))
        data = self._jload()
        return list(data.values())

# single shared store
store = DMReadyStore()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

# ---------- helper you call from other handlers ----------
async def mark_dm_ready_from_message(m: Message) -> None:
    """Idempotent: records first time we ever saw this user in DM."""
    if not m or not m.from_user:
        return
    u = m.from_user
    store.ensure_dm_ready_first_seen(
        user_id=u.id,
        username=u.username or "",
        first_name=u.first_name or "",
        last_name=u.last_name or "",
        when_iso_now_utc=_iso_now_utc(),
    )

# ---------- owner/admin command ----------
def register(app: Client):
    @app.on_message(filters.private & filters.user(OWNER_ID) & filters.command("dmreadylist"))
    async def _dmreadylist(_: Client, m: Message):
        users = store.all()
        # sort by first_marked_iso (oldest first)
        def _key(rec: Dict) -> Tuple[str, int]:
            return (rec.get("first_marked_iso") or "", rec.get("user_id") or 0)
        users.sort(key=_key)

        if not users:
            await m.reply_text("✅ DM-ready users: none yet.")
            return

        lines: List[str] = ["✅ *DM-ready users* —"]
        for i, r in enumerate(users, start=1):
            uid = r.get("user_id")
            un = r.get("username") or ""
            first_seen_la = _iso_to_la_str(r.get("first_marked_iso") or "")
            if un:
                who = f"@{un} — {uid}"
            else:
                who = f"{uid}"
            lines.append(f"{i}. {who} — {first_seen_la}")

        await m.reply_text("\n".join(lines), disable_web_page_preview=True)
