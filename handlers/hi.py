# handlers/hi.py
# Simple warm-up: replies with a short greeting (by name) and touches the chat.

from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):

    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, m: Message):
        name = (m.from_user.first_name if m.from_user else "there")
        # Short, clean warm-up reply; still "touches" the chat to keep it active
        await m.reply_text(f"👋 Hey {name}! This is just a warm-up command.")
