# utils/decorators.py
from pyrogram import filters
from pyrogram.types import Message
from functools import wraps

SUPER_ADMIN_ID = 6964994611

def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        user = message.from_user
        if not user:
            return
        is_admin = (user.id == SUPER_ADMIN_ID) or \
            (await client.get_chat_member(message.chat.id, user.id)).status in ("administrator", "creator")
        if not is_admin:
            return await message.reply("❌ You’re not allowed to use this.")
        return await func(client, message, *args, **kwargs)
    return wrapper

