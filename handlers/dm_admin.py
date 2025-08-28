# handlers/dm_admin.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from utils.dmready_store import DMReadyStore
from utils.admin_check import is_owner_or_admin  # <-- now exists

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
ME_USERNAME = os.getenv("BOT_USERNAME", "")

_store = DMReadyStore()

def register(app: Client):

    @app.on_message(filters.command("dmreadylist"))
    async def dmready_list(client: Client, m: Message):
        if not await is_owner_or_admin(client, m.from_user):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return
        rows = _store.get_all_dm_ready_global()
        if not rows:
            await m.reply_text("ℹ️ No one is marked DM-ready yet.")
            return
        lines = ["✅ <b>DM-ready users</b>"]
        for i, d in enumerate(rows, 1):
            uname = f"@{d['username']}" if d.get("username") else ""
            lines.append(f"{i}. {d.get('first_name','')} {uname} — {d['user_id']}")
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.command("dmnow"))
    async def dm_now(client: Client, m: Message):
        if not await is_owner_or_admin(client, m.from_user):
            await m.reply_text("❌ You’re not allowed to use this command.")
            return
        me = await client.get_me()
        uname = me.username or ME_USERNAME
        url = f"https://t.me/{uname}?start=ready" if uname else "https://t.me"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 Open DM Portal", url=url)]])
        await m.reply_text("Tap to DM the bot:", reply_markup=kb, disable_web_page_preview=True)
