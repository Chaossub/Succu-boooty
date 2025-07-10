from pyrogram import Client
from pyrogram.types import ChatMember

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member: ChatMember = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        print(f"[AdminCheck] Error checking admin: {e}")
        return False
