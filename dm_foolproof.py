# dm_foolproof.py
import os, json
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from handlers.panels import render_main  # single UI router for /start etc.

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DM_FILE = DATA_DIR / "dm_ready.json"


def _load_store() -> dict:
    if DM_FILE.exists():
        try:
            return json.loads(DM_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_store(d: dict) -> None:
    DM_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _mark_dm_ready_once(user_id: int, name: str, username: str | None) -> bool:
    """
    Returns True only the FIRST time a user becomes DM-ready.
    Persists to data/dm_ready.json so it survives restarts.
    """
    store = _load_store()
    users = store.setdefault("users", {})
    key = str(user_id)
    if key in users:
        return False

    users[key] = {
        "name": name,
        "username": username or "",
        "since": datetime.utcnow().isoformat() + "Z",
    }
    _save_store(store)
    return True


def _fmt_user_line(user) -> str:
    un = f"@{user.username}" if user and user.username else ""
    nm = user.first_name or "Someone"
    return f"{nm} {un}".strip()


def register(app: Client):
    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        u = m.from_user
        first_time = _mark_dm_ready_once(u.id, (u.first_name or "Someone"), u.username)

        if first_time:
            # Let the user know (one time only)
            await m.reply_text(f"✅ DM-ready — {_fmt_user_line(u)}")
            # Notify owner (if configured)
            try:
                owner = int(os.getenv("OWNER_ID", "0") or "0")
                if owner:
                    await client.send_message(
                        owner,
                        (
                            "✅ DM-ready NEW user\n"
                            f"• {u.first_name or ''} @{u.username or ''}\n"
                            f"• id: <code>{u.id}</code>"
                        ),
                    )
            except Exception:
                pass

        # Hand off to the main panel UI
        placeholder = await m.reply_text("…")
        await render_main(placeholder)
