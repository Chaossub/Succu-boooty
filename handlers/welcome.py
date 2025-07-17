import logging
from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated

logger = logging.getLogger(__name__)

OWNER_ID = 6964994611  # Hardwired admin owner

def is_join(event: ChatMemberUpdated) -> bool:
    # Defensive: Both must not be None and have .status
    return (
        event.old_chat_member is not None
        and event.new_chat_member is not None
        and hasattr(event.old_chat_member, 'status')
        and hasattr(event.new_chat_member, 'status')
        and event.old_chat_member.status in ("left", "kicked")
        and event.new_chat_member.status in ("member", "administrator")
    )

def is_leave(event: ChatMemberUpdated) -> bool:
    return (
        event.old_chat_member is not None
        and event.new_chat_member is not None
        and hasattr(event.old_chat_member, 'status')
        and hasattr(event.new_chat_member, 'status')
        and event.old_chat_member.status in ("member", "administrator")
        and event.new_chat_member.status in ("left", "kicked")
    )

def register(app: Client):
    @app.on_chat_member_updated()
    async def welcome_goodbye_handler(client, event: ChatMemberUpdated):
        try:
            user = event.new_chat_member.user
            chat_id = event.chat.id

            if is_join(event):
                # Custom logic: Only owner gets special greeting
                if user.id == OWNER_ID:
                    await client.send_message(chat_id, f"👑 The boss <b>{user.mention()}</b> has entered the chat!", parse_mode="HTML")
                else:
                    await client.send_message(chat_id, f"👋 Welcome, <b>{user.mention()}</b>!", parse_mode="HTML")
            elif is_leave(event):
                await client.send_message(chat_id, f"😢 <b>{user.mention()}</b> has left us.", parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error in welcome/goodbye handler: {e}", exc_info=True)
