from pyrogram import filters, Client
from pyrogram.types import Message

def register(app: Client):
    @app.on_message(filters.command("getid"))
    async def get_id(_, message: Message):
        await message.reply_text(f"Your ID: `{message.from_user.id}`\nChat ID: `{message.chat.id}`", parse_mode="markdown")
