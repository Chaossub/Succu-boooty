import json
import time
from pyrogram import filters
from pyrogram.types import Message
from datetime import datetime

WARNINGS_PATH = "data/warnings.json"
SUPER_ADMIN_ID = 6964994611

def load_warns():
    with open(WARNINGS_PATH, "r") as f:
        return json.load(f)

def save_warns(data):
    with open(WARNINGS_PATH, "w") as f:
        json.dump(data, f)

def is_admin(app, user_id, chat_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

def register(app):
    # Warn
    @app.on_message(filters.command("warn") & filters.reply & filters.group)
    async def warn_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can warn users.")
        user = message.reply_to_message.from_user
        chat_id = str(message.chat.id)
        warns = load_warns()
        warns.setdefault(chat_id, {})
        warns[chat_id].setdefault(str(user.id), 0)
        warns[chat_id][str(user.id)] += 1
        save_warns(warns)
        count = warns[chat_id][str(user.id)]
        await message.reply(f"⚠️ {user.mention} has been warned ({count}/6)!")
        # Auto-mute at 3 and 6 warns
        if count == 3:
            try:
                await client.restrict_chat_member(
                    int(chat_id), user.id,
                    permissions=None,
                    until_date=int(time.time()) + 300  # 5 mins
                )
                await message.reply(f"🔇 {user.mention} has been muted for 5 minutes (3 warns)!")
            except Exception as e:
                await message.reply(f"Failed to mute: {e}")
        elif count == 6:
            try:
                await client.restrict_chat_member(
                    int(chat_id), user.id,
                    permissions=None,
                    until_date=int(time.time()) + 600  # 10 mins
                )
                await message.reply(f"🔇 {user.mention} has been muted for 10 minutes (6 warns)!")
            except Exception as e:
                await message.reply(f"Failed to mute: {e}")

    # Flirty warn (does not increment real warns)
    @app.on_message(filters.command("flirtywarn") & filters.reply & filters.group)
    async def flirty_warn(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can use flirty warn.")
        user = message.reply_to_message.from_user
        import random
        messages = [
            f"👀 {user.mention}, that's a spicy move! Just a flirty warning this time... 😘",
            f"💋 {user.mention}, you've caught my attention. Try not to be too naughty!",
            f"😈 {user.mention}, you're on thin ice, but in a fun way...",
            f"🔥 {user.mention}, keep this up and I might have to pay extra attention to you!"
        ]
        await message.reply(random.choice(messages))

    # Warns count
    @app.on_message(filters.command("warns") & filters.reply & filters.group)
    async def check_warns(client, message: Message):
        user = message.reply_to_message.from_user
        chat_id = str(message.chat.id)
        warns = load_warns()
        count = warns.get(chat_id, {}).get(str(user.id), 0)
        await message.reply(f"{user.mention} has {count} warning(s).")

    # Reset warns
    @app.on_message(filters.command("resetwarns") & filters.reply & filters.group)
    async def reset_warns(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can reset warnings.")
        user = message.reply_to_message.from_user
        chat_id = str(message.chat.id)
        warns = load_warns()
        if chat_id in warns and str(user.id) in warns[chat_id]:
            warns[chat_id][str(user.id)] = 0
            save_warns(warns)
            await message.reply(f"✅ Warnings for {user.mention} have been reset.")
        else:
            await message.reply(f"{user.mention} has no warnings.")

    # Mute
    @app.on_message(filters.command("mute") & filters.reply & filters.group)
    async def mute_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can mute users.")
        user = message.reply_to_message.from_user
        args = message.text.split()
        minutes = 0
        if len(args) > 1:
            try:
                minutes = int(args[1])
            except Exception:
                pass
        until = int(time.time()) + (minutes * 60) if minutes > 0 else None
        try:
            await client.restrict_chat_member(
                message.chat.id, user.id, permissions=None, until_date=until
            )
            if minutes > 0:
                await message.reply(f"🔇 {user.mention} muted for {minutes} minute(s)!")
            else:
                await message.reply(f"🔇 {user.mention} muted indefinitely!")
        except Exception as e:
            await message.reply(f"Failed to mute: {e}")

    # Unmute
    @app.on_message(filters.command("unmute") & filters.reply & filters.group)
    async def unmute_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can unmute users.")
        user = message.reply_to_message.from_user
        from pyrogram.types import ChatPermissions
        try:
            await client.restrict_chat_member(
                message.chat.id, user.id, permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                )
            )
            await message.reply(f"🔈 {user.mention} unmuted!")
        except Exception as e:
            await message.reply(f"Failed to unmute: {e}")

    # Ban
    @app.on_message(filters.command("ban") & filters.reply & filters.group)
    async def ban_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can ban users.")
        user = message.reply_to_message.from_user
        try:
            await client.ban_chat_member(message.chat.id, user.id)
            await message.reply(f"🚫 {user.mention} has been banned from the group!")
        except Exception as e:
            await message.reply(f"Failed to ban: {e}")

    # Unban
    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can unban users.")
        args = message.text.split()
        if len(args) < 2 and not message.reply_to_message:
            return await message.reply("Reply to a user or use /unban <user_id>")
        if message.reply_to_message:
            user = message.reply_to_message.from_user
            user_id = user.id
        else:
            try:
                user_id = int(args[1])
            except Exception:
                return await message.reply("Please provide a valid user ID.")
        try:
            await client.unban_chat_member(message.chat.id, user_id)
            await message.reply("✅ User unbanned!")
        except Exception as e:
            await message.reply(f"Failed to unban: {e}")

    # Kick (ban+unban)
    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can kick users.")
        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            args = message.text.split()
            if len(args) < 2:
                return await message.reply("Usage: /kick (reply to a user or provide @username/userid)")
            mention = args[1]
            try:
                if mention.startswith("@"):
                    user = await client.get_users(mention)
                else:
                    user = await client.get_users(int(mention))
            except Exception:
                return await message.reply("Could not find that user.")
        chat_id = message.chat.id
        user_id = user.id
        try:
            await client.ban_chat_member(chat_id, user_id)
            await client.unban_chat_member(chat_id, user_id)
            await message.reply(f"✅ {user.mention} has been kicked from the group!")
        except Exception as e:
            await message.reply(f"Failed to kick: {e}")

    # Userinfo
    @app.on_message(filters.command("userinfo") & filters.group)
    async def userinfo(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("Only admins can use this command.")

        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            args = message.text.split()
            if len(args) < 2:
                return await message.reply(
                    "Usage: /userinfo (reply to user or /userinfo @username or user_id)"
                )
            try:
                mention = args[1]
                if mention.startswith("@"):
                    user = await client.get_users(mention)
                else:
                    user = await client.get_users(int(mention))
            except Exception:
                return await message.reply("Could not find that user.")

        try:
            member = await client.get_chat_member(message.chat.id, user.id)
            joined_date = getattr(member, "joined_date", None)
            joined_str = (
                datetime.utcfromtimestamp(joined_date).strftime('%Y-%m-%d %H:%M:%S')
                if joined_date else "Unknown"
            )
            is_group_admin = member.status in ["administrator", "creator"]
        except Exception:
            joined_str = "Unknown"
            is_group_admin = False

        text = (
            f"<b>User Info:</b>\n"
            f"• Name: {user.mention}\n"
            f"• ID: <code>{user.id}</code>\n"
            f"• Username: @{user.username if user.username else 'None'}\n"
            f"• Group Admin: {'Yes' if is_group_admin else 'No'}\n"
            f"• Joined: {joined_str}"
        )
        await message.reply(text)

