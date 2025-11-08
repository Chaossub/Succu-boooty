# handlers/dm_ready.py
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils.dmready_store import global_store as store

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def register(app: Client):
    # The ONLY /start
    @app.on_message(filters.command("start"))
    async def _start(client: Client, m: Message):
        u = m.from_user
        if u and not u.is_bot:
            created, doc = store.mark(u.id, u.first_name or "User", u.username)
            if created and OWNER_ID:
                handle = f"@{u.username}" if u.username else ""
                when = doc.get("first_seen", "—")
                try:
                    await client.send_message(
                        OWNER_ID,
                        f"✅ <b>DM-ready</b>: {u.first_name} {handle}\n"
                        f"<code>{u.id}</code> • {when}"
                    )
                except Exception:
                    pass

        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_home_kb(),
            disable_web_page_preview=True,
        )
