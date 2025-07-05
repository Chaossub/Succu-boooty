import logging
import random
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

logging.basicConfig(level=logging.DEBUG)

OWNER_ID = 6964994611

FLIRTY_WARN_MESSAGES = [
    "Oh naughty! {mention}, that’s a little spicy for the Sanctuary 😉",
    "{mention}, watch out! The succubi are watching your every move 😈",
    "Careful, {mention}… temptation isn’t always kind 😘",
    "Flirty warning for {mention}! Time to behave… or not 😜",
    "{mention}, you’re treading on thin ice… but we like it 🔥"
]

def is_admin(chat_member, user_id):
    if user_id == OWNER_ID:
        return True
    return chat_member and chat_member.status in ("administrator", "creator")

def register(app):

    async def get_target_user(message: Message):
        if not message.reply_to_message:
            await message.reply("You must reply to the user for this command.")
            logging.debug("Command failed: no reply_to_message")
            return None
        user = message.reply_to_message.from_user
        if not user or not user.id:
            await message.reply("Could not find the user to target.")
            logging.debug("Command failed: reply_to_message has no valid user")
            return None
        return user

    @app.on_message(filters.command("flirtywarn") & filters.group)
    async def flirty_warn(client, message: Message):
        logging.debug(f"Received /flirtywarn from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can send flirty warnings.")
            return
        user = await get_target_user(message)
        if not user:
            return
        msg = random.choice(FLIRTY_WARN_MESSAGES).format(mention=user.mention)
        await message.reply(msg)

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        logging.debug(f"Received /warn from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can issue warnings.")
            return
        user = await get_target_user(message)
        if not user:
            return
        # TODO: implement warning increment in storage
        await message.reply(f"{user.mention} has been warned.")

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        logging.debug(f"Received /mute from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can mute users.")
            return
        user = await get_target_user(message)
        if not user:
            return
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
        logging.debug(f"Received /unmute from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can unmute users.")
            return
        user = await get_target_user(message)
        if not user:
            return
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
        logging.debug(f"Received /kick from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can kick users.")
            return
        user = await get_target_user(message)
        if not user:
            return
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
        logging.debug(f"Received /ban from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can ban users.")
            return
        user = await get_target_user(message)
        if not user:
            return
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply(f"{user.mention} has been banned from the group.")
            logging.debug(f"User {user.id} banned successfully")
        except Exception as e:
            logging.error(f"Failed to ban user {user.id}: {e}", exc_info=True)
            await message.reply(f"Failed to ban: {e}")

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        logging.debug(f"Received /unban from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can unban users.")
            return
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
