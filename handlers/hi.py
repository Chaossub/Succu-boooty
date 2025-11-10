# handlers/hi.py
# Simple warm-up + start: replies and "touches" the chat.

from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):

    # Warm-up command
    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, m: Message):
        name = (m.from_user.first_name if m.from_user else "there")
        await m.reply_text(f"👋 Hey {name}! This is just a warm-up command.")

    # Start command (no new handlers elsewhere; this just restores your welcome)
    @app.on_message(filters.command("start"))
    async def start_handler(client: Client, m: Message):
        await m.reply_text(
            "🔥 <b>Welcome to SuccuBot</b>\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "✨ Type <b>/menu</b> to open the model menu.\n"
            "If you don’t see the buttons after that, send me <b>/hi</b> once to warm me up."
        )
