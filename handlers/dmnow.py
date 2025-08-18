import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("dmnow")

def register(app: Client):
    @app.on_message(filters.command("dmnow"))
    async def dmnow(client: Client, m: Message):
        try:
            me = await client.get_me()
            if not me.username:
                return await m.reply_text("⚠️ I need a @username to create a DM button.")

            url = f"https://t.me/{me.username}?start=ready"
            btn_text = os.getenv("DMNOW_BTN", "💌 DM the Bot")
            caption = os.getenv(
                "DMNOW_TEXT",
                "Tap to DM — open me in private and press Start to get set up."
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=url)]])
            await m.reply_text(caption, reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.exception("/dmnow failed: %s", e)
            await m.reply_text("Couldn’t build the DM button right now.")
