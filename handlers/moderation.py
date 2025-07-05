import logging
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

def register(app):

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        logging.debug(f"Received /mute command from user {message.from_user.id} in chat {message.chat.id}")
        if not message.reply_to_message:
            await message.reply("Reply to a user to mute them.")
            logging.debug("Mute failed: no reply_to_message")
            return
        user = message.reply_to_message.from_user
        try:
            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                ),
                until_date=None
            )
            await message.reply(f"{user.mention} has been muted.")
            logging.debug(f"User {user.id} muted successfully")
        except Exception as e:
            logging.error(f"Failed to mute user {user.id}: {e}", exc_info=True)
            await message.reply(f"Failed to mute: {e}")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user(client, message: Message):
        logging.debug(f"Received /unmute command from user {message.from_user.id} in chat {message.chat.id}")
        if not message.reply_to_message:
            await message.reply("Reply to a user to unmute them.")
            logging.debug("Unmute failed: no reply_to_message")
            return
        user = message.reply_to_message.from_user
        try:
            await client.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await message.reply(f"{user.mention} has been unmuted.")
            logging.debug(f"User {user.id} unmuted successfully")
        except Exception as e:
            logging.error(f"Failed to unmute user {user.id}: {e}", exc_info=True)
            await message.reply(f"Failed to unmute: {e}")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        logging.debug(f"Received /kick command from user {message.from_user.id} in chat {message.chat.id}")
        if not message.reply_to_message:
            await message.reply("Reply to a user to kick them.")
            logging.debug("Kick failed: no reply_to_message")
            return
        user = message.reply_to_message.from_user
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply(f"{user.mention} has been kicked from the group.")
            logging.debug(f"User {user.id} kicked successfully")
        except Exception as e:
            logging.error(f"Failed to kick user {user.id}: {e}", exc_info=True)
            await message.reply(f"Failed to kick: {e}")

    @app.on_message(filters.command("ban") & filters.group)
    async def ban_user(client, message: Message):
        logging.debug(f"Received /ban command from user {message.from_user.id} in chat {message.chat.id}")
        if not message.reply_to_message:
            await message.reply("Reply to a user to ban them.")
            logging.debug("Ban failed: no reply_to_message")
            return
        user = message.reply_to_message.from_user
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply(f"{user.mention} has been banned from the group.")
            logging.debug(f"User {user.id} banned successfully")
        except Exception as e:
            logging.error(f"Failed to ban user {user.id}: {e}", exc_info=True)
            await message.reply(f"Failed to ban: {e}")

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        logging.debug(f"Received /unban command from user {message.from_user.id} in chat {message.chat.id}")
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /unban <user_id>")
            logging.debug("Unban failed: no user_id argument")
            return
        try:
            user_id = int(args[1])
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"User with ID <code>{user_id}</code> has been unbanned.")
            logging.debug(f"User {user_id} unbanned successfully")
        except Exception as e:
            logging.error(f"Failed to unban user {args[1]}: {e}", exc_info=True)
            await message.reply(f"Failed to unban: {e}")
