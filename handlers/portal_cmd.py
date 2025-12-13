# handlers/portal_cmd.py
import os

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


async def _get_bot_username(client: Client) -> str:
    """Prefer env BOT_USERNAME; fallback to get_me()."""
    env_name = (os.getenv("BOT_USERNAME") or "").lstrip("@").strip()
    if env_name:
        return env_name
    try:
        me = await client.get_me()
        return (me.username or "").lstrip("@").strip()
    except Exception:
        return ""


def register(app: Client):
    @app.on_message(filters.command(["portal", "dmnow", "go"]))
    async def _portal_cmd(client: Client, message: Message):
        bot_username = await _get_bot_username(client)
        if not bot_username:
            await message.reply_text(
                "I can’t build the DM button yet because BOT_USERNAME isn’t set.\n\n"
                "Set env <code>BOT_USERNAME</code> to your bot’s @username (without the @) and redeploy.",
                disable_web_page_preview=True,
            )
            return

        url = f"https://t.me/{bot_username}?start=portal"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💌 DM SuccuBot Now", url=url)]])

        await message.reply_text(
            "Tap below to open SuccuBot in your DMs 💋",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
