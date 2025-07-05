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

async def get_user_from_username_or_id(client, chat_id, user_arg):
    try:
        clean_user_arg = user_arg.lstrip("@")
        chat_member = None
        if clean_user_arg.isdigit():
            chat_member = await client.get_chat_member(chat_id, int(clean_user_arg))
        else:
            chat_member = await client.get_chat_member(chat_id, clean_user_arg)

        if chat_member and chat_member.user:
            return chat_member.user

        # Fallback to global get_users()
        return await client.get_users(user_arg)
    except Exception as e:
        logging.debug(f"get_user_from_username_or_id error: {e}")
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
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can send flirty warnings.")
            return
        user = await get_target_user(client, message)
        if not user:
            return
        msg = random.choice(FLIRTY_WARN_MESSAGES).format(mention=user.mention)
        await message.reply(m
