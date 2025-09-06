# dm_foolproof.py
# /start:
#   - marks DM-ready once (persisted)
#   - ALWAYS shows your welcome + buttons
#   - DM-ready banner only on first time
# /dmreadylist shows name, @username, id, since
# Optional cleanup from SANCTUARY_GROUP_IDS on leave/kick

import os
import json
import time
from pathlib import Path
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated

# import the renderer for your main panel (no duplication)
from handlers.panels import main_menu  # <- this shows the welcome + buttons

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
READY_FILE = DATA_DIR / "dm_ready.json"  # { "<uid>": {since, first_name, username} }

def _load_ready() -> Dict[str, dict]:
    if not READY_FILE.exists():
        return {}
    try:
        return json.loads(READY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_ready(d: Dict[str, dict]) -> None:
    tmp = READY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(READY_FILE)

def _ids_from_env(name: str) -> set[int]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out

SANCTUARY_GROUP_IDS = _ids_from_env("SANCTUARY_GROUP_IDS")

def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def _start(c: Client, m: Message):
        """Mark DM-ready once, but ALWAYS show the main menu panel."""
        u = m.from_user
        if not u:
            return

        store = _load_ready()
        key = str(u.id)
        first_time = key not in store

        if first_time:
            store[key] = {
                "since": int(time.time()),
                "first_name": (u.first_name or "").strip() or "Someone",
                "username": (u.username or "") or "",
            }
            _save_ready(store)
            # one-time banner
            name = store[key]["first_name"]
            uname = f"@{store[key]['username']}" if store[key]["username"] else ""
            await m.reply_text(f"✅ DM-ready — {name} {uname}".rstrip())

        # ALWAYS render the welcome + buttons (no duplicates)
        await main_menu(m)

    @app.on_message(filters.command("dmreadylist", prefixes=["/", "!", "."]))
    async def _dm_list(c: Client, m: Message):
        store = _load_ready()
        if not store:
            return await m.reply_text("📬 DM-ready (all)\n• <i>none yet</i>")

        lines = []
        for uid, info in sorted(store.items(), key=lambda kv: kv[1].get("since", 0)):
            name = info.get("first_name") or "Someone"
            uname = info.get("username")
            handle = f"@{uname}" if uname else ""
            since = info.get("since", 0)
            lines.append(
                f"• <a href='tg://user?id={uid}'>{name}</a> {handle} — id: <code>{uid}</code> — since <code>{since}</code>"
            )
        await m.reply_text("📬 <b>DM-ready (all)</b>\n" + "\n".join(lines),
                           disable_web_page_preview=True)

    # Optional auto-cleanup if a user leaves/kicked/banned from your sanctuary groups
    if SANCTUARY_GROUP_IDS:
        @app.on_chat_member_updated()
        async def _cleanup(c: Client, upd: ChatMemberUpdated):
            try:
                if upd.chat.id not in SANCTUARY_GROUP_IDS:
                    return
                new = upd.new_chat_member
                if not new or not new.user:
                    return
                user_id = str(new.user.id)
                if new.status in {"kicked", "left", "banned"}:
                    store = _load_ready()
                    if user_id in store:
                        store.pop(user_id, None)
                        _save_ready(store)
            except Exception:
                pass

