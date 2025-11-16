# handlers/portal_cmd.py
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

BOT_USERNAME = "Succubot_bot"

def register(app: Client):

    @app.on_message(filters.command(["portal", "dmnow", "go"]) )
    async def _portal_cmd(client: Client, message: Message):

        url = f"https://t.me/{BOT_USERNAME}?start=portal"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💌 DM SuccuBot Now", url=url)]
        ])

        await message.reply_text(
            "Tap below to open SuccuBot in your DMs 💋",
            reply_markup=kb,
            disable_web_page_preview=True
        )
