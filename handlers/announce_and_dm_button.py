# handlers/announce_and_dm_button.py
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 🔹 Load announcement text from environment
MEN_ANNOUNCEMENT = os.getenv(
    "MEN_ANNOUNCEMENT",
    "⚠️ No announcement text set. Please configure MEN_ANNOUNCEMENT in your environment."
)

def build_dm_button(bot_username: str):
    deep_link = f"https://t.me/{bot_username}?start=dm"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💌 DM Now", url=deep_link)]]
    )

# ---------- Handlers ----------
def register(app: Client):
    # /announce_men command
    @app.on_message(filters.command("announce_men") & filters.user(int(os.getenv("OWNER_ID", "6964994611"))))
    async def announce_men(client, message):
        markup = build_dm_button((await client.get_me()).username)
        await message.chat.send_message(
            MEN_ANNOUNCEMENT,
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    # /dmnow command (button only, no text)
    @app.on_message(filters.command("dmnow") & filters.user(int(os.getenv("OWNER_ID", "6964994611"))))
    async def dmnow(client, message):
        markup = build_dm_button((await client.get_me()).username)
        await message.chat.send_message(
            "Click below to DM the bot:",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    # /start handler with deep-link (?start=dm)
    @app.on_message(filters.command("start"))
    async def start_handler(client, message):
        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].lower() == "dm":
            await message.reply_text(
                "💌 You’re now DM ready with SuccuBot!\n\n"
                "Use the menu to see model menus, buyer rules, game rules, "
                "or message an admin anonymously. 😈"
            )
        else:
            await message.reply_text(
                "🔥 Welcome to SuccuBot — your hub for menus, rules, games, and more!"
            )
