# handlers/dmnow.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

async def _bot_username(client: Client) -> str:
    env = (os.getenv("BOT_USERNAME") or "").lstrip("@").strip()
    if env:
        return env
    me = await client.get_me()
    return (me.username or "").lstrip("@").strip()

def register(app: Client):
    log.info("✅ dmnow handler registered")

    @app.on_message(filters.command(["dmnow"]) & filters.group)
    async def dmnow_cmd(client: Client, message: Message):
        uname = await _bot_username(client)
        if not uname:
            await message.reply_text("BOT_USERNAME is not set, so I can't build the DM link.")
            return
        url = f"https://t.me/{uname}?start=portal"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM SuccuBot Now", url=url)]])
        await message.reply_text("Tap below to open SuccuBot Sanctuary mode in DMs 😈", reply_markup=kb)

    # quick sanity check command so we can prove the module is loaded
    @app.on_message(filters.command(["dmnowtest"]) & filters.group)
    async def dmnow_test(_, message: Message):
        await message.reply_text("✅ /dmnow module is loaded + firing.")
