# handlers/portal_cmd.py
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


async def _get_bot_username(client: Client) -> str:
    env_name = (os.getenv("BOT_USERNAME") or "").lstrip("@").strip()
    if env_name:
        return env_name
    me = await client.get_me()
    return (me.username or "").lstrip("@").strip()


def register(app: Client):
    # /portal (GROUP) -> opens Roni Assistant in DMs
    @app.on_message(filters.command(["portal"]) & filters.group)
    async def portal_cmd(client: Client, message: Message):
        bot_username = await _get_bot_username(client)
        if not bot_username:
            await message.reply_text(
                "BOT_USERNAME is not set, so I can’t build the DM button yet.\n"
                "Set env <code>BOT_USERNAME</code> to your bot’s @username (without @) and redeploy.",
                disable_web_page_preview=True,
            )
            return

        url = f"https://t.me/{bot_username}?start=roni_assistant"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💋 DM Roni Assistant", url=url)]])

        await message.reply_text(
            "Tap below to open Roni’s assistant in your DMs 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
