# handlers/dmnow.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

async def _bot_username(client: Client) -> str:
    env = (os.getenv("BOT_USERNAME") or "").lstrip("@").strip()
    if env:
        return env
    me = await client.get_me()
    return (me.username or "").lstrip("@").strip()

def register(app: Client):
    # GROUP: /dmnow should open SuccuBot Sanctuary mode in DMs
    @app.on_message(filters.command(["dmnow"]) & filters.group)
    async def dmnow_cmd(client: Client, message: Message):
        uname = await _bot_username(client)
        if not uname:
            await message.reply_text("Set BOT_USERNAME env var to your bot’s username.")
            return
        url = f"https://t.me/{uname}?start=portal"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM SuccuBot Now", url=url)]])
        await message.reply_text(
            "Tap below to slide into my DMs, cutie 😈",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
