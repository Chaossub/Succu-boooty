from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from functools import wraps

def admin_only(func):
    @wraps(func)
    async def wrapper(client, message: Message):
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            return await message.reply("🚫 You must be an admin to use this command.")
        return await func(client, message)
    return wrapper
