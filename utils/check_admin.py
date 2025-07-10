from pyrogram import Client

SUPER_ADMIN_ID = 6964994611  # Replace with your actual Telegram ID if needed

async def is_admin(user, chat) -> bool:
    if not user:
        return False
    if user.id == SUPER_ADMIN_ID:
        return True
    try:
        async for member in chat.get_members():
            if member.user.id == user.id and member.status in ("administrator", "creator"):
                return True
    except:
        pass
    return False
