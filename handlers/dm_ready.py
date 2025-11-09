# handlers/dm_ready.py
from __future__ import annotations
import os
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

WELCOME = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep "
    "things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def register(app: Client):

    @app.on_message(filters.command("start"))
    async def _start(client: Client, m: Message):
        # Mark user DM-ready (first time only) – survives restart via JSON
        u = m.from_user or m.chat
        if u and not u.is_bot:
            rec = store.mark(
                user_id=u.id,
                first_name=(u.first_name or "User"),
                username=u.username,
                when_iso_utc=_now_iso_utc(),
            )
            # quiet badge to show it worked (optional)
            try:
                handle = f"@{rec['username']}" if rec.get("username") else ""
                when = rec["first_marked_iso"]
                await m.reply_text(
                    f"✅ DM-ready: <b>{rec['first_name']}</b> {handle}\n<code>{rec['id']}</code> • {when}",
                    disable_web_page_preview=True
                )
            except Exception:
                pass

        # Main home message
        await m.reply_text(
            WELCOME,
            disable_web_page_preview=True,
            reply_markup=None  # your keyboard if you have one
        )
