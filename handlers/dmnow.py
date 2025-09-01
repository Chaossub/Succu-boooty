# handlers/dmnow.py
# /dmnow -> posts a deep-link button to open the bot DM portal.
# Duplicate-safe (per message) and duplicate-safe (module wire). No side effects.

import os
from typing import Set, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

BOT_USERNAME = os.getenv("BOT_USERNAME")  # optional; falls back to get_me().username

_processed: Set[Tuple[int, int]] = set()
_REGISTERED = False

def _need_skip(m: Message) -> bool:
    key = (m.chat.id, m.id)
    if key in _processed:
        return True
    _processed.add(key)
    if len(_processed) > 1000:
        _processed.clear()
        _processed.add(key)
    return False

def register(app: Client):
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        if _need_skip(m):
            return

        me = await client.get_me()
        username = BOT_USERNAME or (me.username if me else None)
        if not username:
            await m.reply_text("⚠️ Bot username isn’t set. Set BOT_USERNAME or give the bot an @username.")
            return

        url = f"https://t.me/{username}?start=ready"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 Open DM Portal", url=url)]])
        await m.reply_text(
            "Tap below to open the DM portal:\n"
            f"<code>{url}</code>",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
