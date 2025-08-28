# handlers/dmnow.py
# /dmnow → deep-link button to your bot (no side-effects)

import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

BOT_USERNAME = os.getenv("BOT_USERNAME")  # without @

def register(app: Client):
    @app.on_message(filters.private & filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        me = await client.get_me()
        username = BOT_USERNAME or me.username
        if not username:
            await m.reply_text("Bot username isn’t set. Set BOT_USERNAME in env.")
            return
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💌 Open DM Portal", url=f"https://t.me/{username}?start=ready")]]
        )
        await m.reply_text("Tap below to open the DM portal:", reply_markup=kb)
