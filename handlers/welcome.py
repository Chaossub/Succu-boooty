import logging
from pyrogram import filters

logger = logging.getLogger(__name__)

def is_join(event):
    # Safely handle NoneTypes
    try:
        return (
            hasattr(event, "new_chat_member")
            and hasattr(event, "old_chat_member")
            and event.old_chat_member
            and event.new_chat_member
            and event.old_chat_member.status in ("left", "kicked")
            and event.new_chat_member.status == "member"
        )
    except Exception as e:
        logger.error(f"is_join check failed: {e}")
        return False

def is_leave(event):
    # Safely handle NoneTypes
    try:
        return (
            hasattr(event, "new_chat_member")
            and hasattr(event, "old_chat_member")
            and event.old_chat_member
            and event.new_chat_member
            and event.old_chat_member.status == "member"
            and event.new_chat_member.status in ("left", "kicked")
        )
    except Exception as e:
        logger.error(f"is_leave check failed: {e}")
        return False

def register(app):
    @app.on_chat_member_updated(filters.group)
    async def welcome_goodbye_handler(client, event):
        try:
            # Guard for invalid events
            if not hasattr(event, "new_chat_member") or not hasattr(event, "old_chat_member"):
                return
            if not event.new_chat_member or not event.old_chat_member:
                return

            # Welcome message
            if is_join(event):
                user = getattr(event.new_chat_member, "user", None)
                if not user:
                    return
                await event.chat.send_message(
                    f"👋 Welcome, {user.mention(style='md')}! Feel free to say hi!"
                )

            # Goodbye message
            elif is_leave(event):
                user = getattr(event.old_chat_member, "user", None)
                if not user:
                    return
                await event.chat.send_message(
                    f"👋 {user.first_name} has left the chat. See you next time!"
                )

        except Exception as e:
            logger.error(f"Error in welcome/goodbye handler: {e}", exc_info=True)
