from pyrogram import Client

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")
