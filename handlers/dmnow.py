# handlers/dmnow.py
# /dmnow -> a single deep-link button to the bot (does NOT mark DM-ready; /start does).

import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

log = logging.getLogger("handlers.dmnow")

def register(app: Client):
    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        me = await client.get_me()
        # send a deep-link with a tiny payload "d" to record source (logic lives in /start)
        url = f"https://t.me/{me.username}?start=d"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 Open DM Portal", url=url)]])
        await m.reply_text("Tap to open your portal:", reply_markup=kb, disable_web_page_preview=True)

