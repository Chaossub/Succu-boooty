# handlers/get_id.py
from pyrogram import filters
from pyrogram.types import Message
from main import app

@app.on_message(filters.command("id") & (filters.group | filters.channel))
async def send_chat_id(client, message: Message):
    await message.reply_text(f"Chat ID: `{message.chat.id}`", quote=True)
