from pyrogram import Client, filters
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.command("start"))
    async def start(client: Client, message: Message):
        await message.reply_text("👋 Hello! I’m alive and ready.")

    @app.on_message(filters.command("ping"))
    async def ping(client: Client, message: Message):
        await message.reply_text("🏓 Pong!")
