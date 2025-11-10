# handlers/hi.py
# Warm-up (/hi) + Start (/start) with a simple reply keyboard that sends /menu

from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

def register(app: Client):

    # Simple warm-up
    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, m: Message):
        name = (m.from_user.first_name if m.from_user else "there")
        await m.reply_text(f"👋 Hey {name}! This is just a warm-up command.")

    # Start with a reply keyboard that posts "/menu"
    @app.on_message(filters.command("start"))
    async def start_handler(client: Client, m: Message):
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("/menu")]],  # this will trigger your existing /menu handler
            resize_keyboard=True,
            selective=True
        )
        # Use Markdown since your Client is ParseMode.MARKDOWN
        await m.reply_text(
            "🔥 **Welcome to SuccuBot**\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Tap **/menu** below to open the model menu.",
            reply_markup=kb,
            disable_web_page_preview=True
        )
