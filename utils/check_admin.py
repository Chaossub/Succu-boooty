from pyrogram import Client

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        print(f"[AdminCheck] User: {user_id} | Chat: {chat_id} | Status: {member.status}")
        return member.status in ("administrator", "creator")
    except Exception as e:
        print(f"[AdminCheck Error] {e}")
        return False
