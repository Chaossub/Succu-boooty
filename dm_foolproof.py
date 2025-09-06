# dm_foolproof.py
import os
import json
import time
from typing import Dict, Any, Optional

from pyrogram import filters
from pyrogram.types import Message

# We only import these helpers – do not touch your panels implementation.
try:
    from handlers.panels import main_welcome_text, get_main_panel
except Exception:
    # Fallback text/keyboard if panels isn't imported for some reason
    def main_welcome_text() -> str:
        return (
            "🔥 Welcome to SuccuBot 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!"
        )
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    def get_main_panel() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💕 Menu", callback_data="nav:menu")],
                [InlineKeyboardButton("👑 Contact Admins", callback_data="nav:admins")],
                [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="nav:models")],
                [InlineKeyboardButton("❓ Help", callback_data="nav:help")],
            ]
        )

# -----------------------------
# Storage with Mongo (preferred) or JSON fallback
# -----------------------------

class _Store:
    def __init__(self) -> None:
        self.use_mongo = False
        self.col = None  # type: ignore
        url = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or ""
        if url:
            try:
                from pymongo import MongoClient, ASCENDING
                cli = MongoClient(url)
                dbname = os.getenv("MONGO_DB", "succubot")
                db = cli[dbname]
                self.col = db["dm_ready"]
                # Guarantee index and uniqueness
                try:
                    self.col.create_index([("id", ASCENDING)], unique=True)
                except Exception:
                    pass
                self.use_mongo = True
            except Exception:
                self.use_mongo = False

        self.json_path = os.getenv("DMREADY_FILE", "dm_ready.json")
        if not self.use_mongo:
            # Ensure file exists
            if not os.path.exists(self.json_path):
                with open(self.json_path, "w") as f:
                    json.dump({}, f)

    # ---------- helpers ----------
    def _jload(self) -> Dict[str, Any]:
        try:
            with open(self.json_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _jsave(self, data: Dict[str, Any]) -> None:
        tmp = self.json_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.json_path)

    # ---------- public API ----------
    def get(self, uid: int) -> Optional[Dict[str, Any]]:
        if self.use_mongo and self.col is not None:
            doc = self.col.find_one({"id": uid})
            return dict(doc) if doc else None
        data = self._jload()
        return data.get(str(uid))

    def set_if_absent(self, rec: Dict[str, Any]) -> bool:
        """
        Insert once. Return True if inserted (first time), False if already existed.
        """
        uid = rec["id"]
        if self.use_mongo and self.col is not None:
            existing = self.col.find_one({"id": uid})
            if existing:
                return False
            # race-safe upsert by id
            self.col.update_one({"id": uid}, {"$setOnInsert": rec}, upsert=True)
            return True

        data = self._jload()
        key = str(uid)
        if key in data:
            return False
        data[key] = rec
        self._jsave(data)
        return True

    def list_all(self) -> Dict[str, Any]:
        if self.use_mongo and self.col is not None:
            rows = {}
            for d in self.col.find({}).sort("since", -1):
                rows[str(d["id"])] = {
                    "id": d["id"],
                    "name": d.get("name"),
                    "username": d.get("username"),
                    "since": d.get("since"),
                }
            return rows
        return self._jload()

STORE = _Store()

def _since_human(ts: float) -> str:
    dt = max(0, int(time.time() - ts))
    d, r = divmod(dt, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    if d: return f"{d}d {h}h"
    if h: return f"{h}h {m}m"
    return f"{m}m"

# -----------------------------
# Registration
# -----------------------------
def register(app):
    @app.on_message(filters.command("start"))
    async def _start(client, msg: Message):
        u = msg.from_user
        uid = u.id

        # Create record ONLY the first time
        first_time = STORE.set_if_absent({
            "id": uid,
            "name": u.first_name or "Someone",
            "username": f"@{u.username}" if u.username else "(no username)",
            "since": time.time(),
        })

        # Show the green banner only once
        if first_time:
            rec = STORE.get(uid) or {}
            await msg.reply_text(
                f"✅ DM-ready — {rec.get('name','Someone')} {rec.get('username','')}".strip()
            )

        # Always show ONE welcome + buttons (no extra info card)
        await msg.reply_text(
            main_welcome_text(),
            reply_markup=get_main_panel(),
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("dmreadylist"))
    async def _list(client, msg: Message):
        rows = STORE.list_all()
        if not rows:
            await msg.reply_text("📭 Nobody is DM-ready yet.")
            return
        # Sort newest first
        sorted_rows = sorted(rows.values(), key=lambda r: r.get("since", 0), reverse=True)
        out = ["📋 **DM-ready (all)**"]
        for r in sorted_rows:
            since = r.get("since")
            since_s = _since_human(since) + " ago" if isinstance(since, (int, float)) else "unknown"
            out.append(f"• {r.get('name','Someone')} {r.get('username','')} — `{r['id']}` — since {since_s}")
        await msg.reply_text("\n".join(out))
