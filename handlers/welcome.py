import logging
from pyrogram import filters

logger = logging.getLogger(__name__)

def register(app):
    @app.on_chat_member_updated(filters.group)
    async def welcome_goodbye_handler(client, event):
        try:
            # Welcome new member
            if (
                event.old_chat_member and
                event.new_chat_member and
                event.old_chat_member.status in ("left", "kicked") and
                event.new_chat_member.status == "member"
            ):
                user = event.new_chat_member.user
                await event.chat.send_message(
                    f"👋 Welcome, {user.mention}! Feel free to say hi!"
                )
            # Goodbye
            elif (
                event.old_chat_member and
                event.new_chat_member and
                event.old_chat_member.status == "member" and
                event.new_chat_member.status in ("left", "kicked")
            ):
                user = event.old_chat_member.user
                await event.chat.send_message(
                    f"👋 {user.first_name} has left the chat. See you next time!"
                )
        except Exception as e:
            logger.error(f"Error in welcome/goodbye handler: {e}", exc_info=True)
