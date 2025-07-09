from functools import wraps
from pyrogram.types import Message

def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        user = await client.get_chat_member(message.chat.id, message.from_user.id)
        if user.status not in ("administrator", "creator"):
            return await message.reply("🚫 You must be an admin to use this command.")
        return await func(client, message, *args, **kwargs)
    return wrapper
