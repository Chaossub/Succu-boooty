from pyrogram import Client
from pyrogram.errors import PeerIdInvalid

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except PeerIdInvalid:
        return False
    except Exception as e:
        print(f"Admin check error: {e}")
        return False
