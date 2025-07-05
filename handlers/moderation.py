from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

def register(app):

    def is_admin(chat_member):
        return chat_member and chat_member.status in ("administrator", "creator")

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can issue warnings.")
            return
        if not message.reply_to_message:
            await message.reply("Reply to a user to warn them.")
            return
        warned_user = message.reply_to_message.from_user
        # TODO: implement warning increment in your storage
        await message.reply(f"{warned_user.mention} has been warned.")

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can mute users.")
            return
        if not message.reply_to_message:
            await message.reply("Reply to a user to mute them.")
            return
        muted_user = message.reply_to_message.from_user
        try:
            await client.restrict_chat_member(
                message.chat.id,
                muted_user.id,
                permissions=ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                ),
                until_date=None  # Indefinite mute
            )
            await message.reply(f"{muted_user.mention} has been muted indefinitely.")
        except Exception as e:
            await message.reply(f"Failed to mute: {e}")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can unmute users.")
            return
        if not message.reply_to_message:
            await message.reply("Reply to a user to unmute them.")
            return
        unmuted_user = message.reply_to_message.from_user
        try:
            await client.restrict_chat_member(
                message.chat.id,
                unmuted_user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await message.reply(f"{unmuted_user.mention} has been unmuted.")
        except Exception as e:
            await message.reply(f"Failed to unmute: {e}")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can kick users.")
            return
        if not message.reply_to_message:
            await message.reply("Reply to a user to kick them.")
            return
        kicked_user = message.reply_to_message.from_user
        try:
            await client.ban_chat_member(message.chat.id, kicked_user.id)
            await client.unban_chat_member(message.chat.id, kicked_user.id)
            await message.reply(f"{kicked_user.mention} has been kicked from the group.")
        except Exception as e:
            await message.reply(f"Failed to kick: {e}")

    @app.on_message(filters.command("ban") & filters.group)
    async def ban_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can ban users.")
            return
        if not message.reply_to_message:
            await message.reply("Reply to a user to ban them.")
            return
        banned_user = message.reply_to_message.from_user
        try:
            await client.ban_chat_member(message.chat.id, banned_user.id)
            await message.reply(f"{banned_user.mention} has been banned from the group.")
        except Exception as e:
            await message.reply(f"Failed to ban: {e}")

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        if not message.from_user:
            return
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member):
            await message.reply("Only admins can unban users.")
            return
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /unban <user_id>")
            return
        try:
            user_id = int(args[1])
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"User with ID <code>{user_id}</code> has been unbanned.")
        except Exception as e:
            await message.reply(f"Failed to unban: {e}")

    # You can extend with warns, resetwarns, etc.

