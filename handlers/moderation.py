import logging
import random
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
)

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

async def get_user_from_username_or_id(client, chat_id, user_arg):
    try:
        clean_user_arg = user_arg.lstrip("@")
        chat_member = None
        if clean_user_arg.isdigit():
            chat_member = await client.get_chat_member(chat_id, int(clean_user_arg))
        else:
            chat_member = await client.get_chat_member(chat_id, clean_user_arg)

        if chat_member and chat_member.user:
            logging.debug(f"Found chat member user: {chat_member.user.id} / {chat_member.user.first_name}")
            return chat_member.user

        logging.debug(f"Chat member lookup failed for: {user_arg}. Trying get_users fallback.")
        user = await client.get_users(user_arg)
        logging.debug(f"get_users fallback found user: {user.id} / {user.first_name}")
        return user
    except Exception as e:
        logging.error(f"Error in get_user_from_username_or_id: {e}", exc_info=True)
        return None

async def get_target_user(client, message: Message):
    args = message.text.split()
    if len(args) >= 2:
        user_arg = args[1]
        user = await get_user_from_username_or_id(client, message.chat.id, user_arg)
        if not user:
            await message.reply("User not found in this chat.")
        return user
    elif message.reply_to_message:
        user = message.reply_to_message.from_user
        if user and user.id:
            return user
        else:
            await message.reply("Replied message has no valid user.")
            return None
    else:
        await message.reply("Please specify a user by username, ID, or reply to their message.")
        return None

def register(app):

    @app.on_message(filters.command("flirtywarn") & filters.group)
    async def flirty_warn(client, message: Message):
        logging.debug(f"Received /flirtywarn from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can send flirty warnings.")
            user = await get_target_user(client, message)
            if not user:
                return
            msg = random.choice(FLIRTY_WARN_MESSAGES).format(mention=user.mention)
            await message.reply(msg)
        except Exception as e:
            logging.error(f"Error in /flirtywarn: {e}", exc_info=True)

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        logging.debug(f"Received /warn from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can issue warnings.")
            user = await get_target_user(client, message)
            if not user:
                return
            # TODO: Add persistent warning storage here
            await message.reply(f"{user.mention} has been warned.")
        except Exception as e:
            logging.error(f"Error in /warn: {e}", exc_info=True)

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        logging.info(f"[MUTE] Command received from user {message.from_user.id} in chat {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            logging.debug(f"[MUTE] Command issuer status: {chat_member.status}")
            if not (chat_member.status in ["administrator", "creator"] or message.from_user.id == OWNER_ID):
                await message.reply("Only admins can mute users.")
                logging.info(f"[MUTE] User {message.from_user.id} is not admin, aborting.")
                return

            target_user = None
            if message.reply_to_message:
                target_user = message.reply_to_message.from_user
                logging.debug(f"[MUTE] Target user from reply: {target_user.id if target_user else 'None'}")
            else:
                args = message.text.split()
                if len(args) < 2:
                    await message.reply("Reply to a user or specify username/ID to mute.")
                    logging.info("[MUTE] No user specified.")
                    return
                try:
                    target_user = await client.get_users(args[1])
                    logging.debug(f"[MUTE] Target user from argument: {target_user.id}")
                except Exception as e:
                    logging.error(f"[MUTE] Failed to fetch user '{args[1]}': {e}", exc_info=True)
                    await message.reply("Could not find the specified user.")
                    return

            if not target_user or not hasattr(target_user, "id"):
                await message.reply("Target user not found or invalid.")
                logging.error("[MUTE] Target user invalid or None.")
                return

            if target_user.is_bot:
                await message.reply("Cannot mute a bot.")
                logging.info(f"[MUTE] Tried to mute bot user {target_user.id}.")
                return
            if target_user.id == message.from_user.id:
                await message.reply("You cannot mute yourself.")
                return
            if target_user.id == OWNER_ID:
                await message.reply("You cannot mute the bot owner.")
                return

            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            )
            logging.debug(f"[MUTE] Restricting user {target_user.id} with permissions: {permissions}")

            # Important: until_date=0 means indefinite mute, avoid None
            await client.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target_user.id,
                permissions=permissions,
                until_date=0
            )
            await message.reply(f"{target_user.mention} has been muted indefinitely.")
            logging.info(f"[MUTE] User {target_user.id} muted successfully.")
        except Exception as e:
            logging.error(f"[MUTE] Exception: {e}", exc_info=True)
            await message.reply(f"Failed to mute: {e}")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user(client, message: Message):
        logging.debug(f"Received /unmute from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can unmute users.")
            user = await get_target_user(client, message)
            if not user:
                return

            await client.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                ),
                until_date=0
            )
            await message.reply(f"{user.mention} has been unmuted.")
            logging.debug(f"User {user.id} unmuted successfully")
        except Exception as e:
            await message.reply(f"Failed to unmute: {e}")
            logging.error(f"Error in /unmute: {e}", exc_info=True)

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        logging.debug(f"Received /kick from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can kick users.")
            user = await get_target_user(client, message)
            if not user:
                return

            await client.ban_chat_member(message.chat.id, user.id)
            await client.unban_chat_member(message.chat.id, user.id)
            await message.reply(f"{user.mention} has been kicked from the group.")
            logging.debug(f"User {user.id} kicked successfully")
        except Exception as e:
            await message.reply(f"Failed to kick: {e}")
            logging.error(f"Error in /kick: {e}", exc_info=True)

    @app.on_message(filters.command("ban") & filters.group)
    async def ban_user(client, message: Message):
        logging.debug(f"Received /ban from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can ban users.")
            user = await get_target_user(client, message)
            if not user:
                return

            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply(f"{user.mention} has been banned from the group.")
            logging.debug(f"User {user.id} banned successfully")
        except Exception as e:
            await message.reply(f"Failed to ban: {e}")
            logging.error(f"Error in /ban: {e}", exc_info=True)

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        logging.debug(f"Received /unban from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can unban users.")
            args = message.text.split()
            if len(args) < 2:
                return await message.reply("Usage: /unban <user_id>")
            user_id = int(args[1])
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply(f"User with ID <code>{user_id}</code> has been unbanned.")
            logging.debug(f"User {user_id} unbanned successfully")
        except Exception as e:
            await message.reply(f"Failed to unban: {e}")
            logging.error(f"Error in /unban: {e}", exc_info=True)

    @app.on_message(filters.command("userinfo") & filters.group)
    async def userinfo(client, message: Message):
        logging.debug(f"Received /userinfo from {message.from_user.id} in {message.chat.id}")
        try:
            chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if not is_admin(chat_member, message.from_user.id):
                return await message.reply("Only admins can use this command.")
            user = await get_target_user(client, message)
            if not user:
                return
            chat_member_info = None
            try:
                chat_member_info = await client.get_chat_member(message.chat.id, user.id)
            except Exception:
                pass
            text = (
                f"<b>User Info:</b>\n"
                f"👤 Name: {user.first_name or ''} {user.last_name or ''}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🔗 Username: @{user.username if user.username else 'None'}\n"
                f"🤖 Bot: {'Yes' if user.is_bot else 'No'}\n"
            )
            if chat_member_info:
                status = chat_member_info.status
                text += f"📋 Status in chat: {status.capitalize()}\n"
                if chat_member_info.custom_title:
                    text += f"⭐ Custom title: {chat_member_info.custom_title}\n"
                if chat_member_info.is_anonymous:
                    text += "🙈 Anonymous admin: Yes\n"
                if chat_member_info.until_date:
                    text += f"⏳ Restricted until: {chat_member_info.until_date}\n"
            await message.reply(text)
        except Exception as e:
            await message.reply(f"Failed to get user info: {e}")
            logging.error(f"Error in /userinfo: {e}", exc_info=True)
