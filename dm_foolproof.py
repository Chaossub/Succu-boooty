# dm_foolproof.py
# Single /start handler that:
# - renders the main panel
# - marks user DM-ready ONLY ONCE (persists across restarts)
# - notifies OWNER_ID only the first time
# - does NOT re-announce on subsequent /start

import os, json
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from handlers.panels import render_main  # reuse the single UI router

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DM_FILE = DATA_DIR / "dm_ready.json"

def _load_store():
    if DM_FILE.exists():
        try:
            return json.loads(DM_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_store(d: dict):
    DM_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def _mark_dm_ready_once(user_id: int, name: str, username: str | None) -> bool:
    store = _load_store()
    if "users" not in store:
        store["users"] = {}
    if str(user_id) in store["users"]:
        # already recorded -> not new
        return False
    store["users"][str(user_id)] = {
        "name": name,
        "username": username or "",
        "since": datetime.utcnow().isoformat() + "Z",
    }
    _save_store(store)
    return True

def _fmt_user_line(user):
    un = f"@{user.username}" if user and user.username else ""
    nm = user.first_name or "Someone"
    return f"{nm} {un}".strip()

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        # 1) Mark DM-ready only if brand-new
        u = m.from_user
        is_new = _mark_dm_ready_once(
            u.id,
            (u.first_name or "Someone"),
            u.username
        )

        # 2) Announce "DM-ready" to the user ONLY the first time
        if is_new:
            await m.reply_text(f"✅ DM-ready — {_fmt_user_line(u)}")

            # Also notify the owner just once
            try:
                if OWNER_ID:
                    await client.send_message(
                        OWNER_ID,
                        f"✅ DM-ready NEW user\n• {u.first_name or ''} @{u.username or ''}\n• id: <code>{u.id}</code>"
                    )
            except Exception:
                pass

        # 3) Render the main menu (edited-in-place style via panels)
        placeholder = await m.reply_text("…")
        await render_main(placeholder)
