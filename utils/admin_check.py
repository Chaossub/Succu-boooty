import os
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

async def is_admin(client, chat_id, user_id):
    if str(user_id) == str(os.getenv("OWNER_ID")):
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except (UserNotParticipant, ChatAdminRequired):
        return False
