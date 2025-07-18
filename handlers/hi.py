from pyrogram import Client, filters
from pyrogram.types import Message

def register(app):
    @app.on_message(filters.command("hi"))
    async def hi_handler(client: Client, message: Message):
        await message.reply("hi!")
