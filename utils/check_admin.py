from pyrogram import Client

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    async for member in client.get_chat_members(chat_id):
        if member.user.id == user_id and member.status in ("administrator", "creator"):
            return True
    return False
