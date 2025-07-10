from pyrogram import Client

# Replace with your actual Telegram user ID
SUPER_ADMIN_ID = 6964994611

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    # Always treat the super admin as admin
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False
