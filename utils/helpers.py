from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus

async def admin_only(_, message: Message):
    member = await message.chat.get_member(message.from_user.id)
    return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
