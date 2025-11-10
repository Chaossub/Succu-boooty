# handlers/hi.py
from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, m: Message):
        name = (m.from_user.first_name if m.from_user else "there")
        await m.reply_text(f"👋 Hey {name}! This is just a warm-up command.")
