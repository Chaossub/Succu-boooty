import os
import json
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

WARNINGS_PATH = "data/warnings.json"
SUPER_ADMIN_ID = 6964994611

def load_warnings():
    with open(WARNINGS_PATH, "r") as f:
        return json.load(f)

def save_warnings(data):
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

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to warn users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to warn them!")
        user_id = str(message.reply_to_message.from_user.id)
        reason = " ".join(message.command[1:]) if len(message.command) > 1 else "No reason given."
        warnings = load_warnings()
        group_id = str(message.chat.id)
        if group_id not in warnings:
            warnings[group_id] = {}
        if user_id not in warnings[group_id]:
            warnings[group_id][user_id] = 0
        warnings[group_id][user_id] += 1
        save_warnings(warnings)
        warn_count = warnings[group_id][user_id]
        await message.reply(f"⚠️ {message.reply_to_message.from_user.mention} has been warned!\nReason: {reason}\nTotal warns: {warn_count}")

        # Automute on 3/6 warns
        mute_time = None
        if warn_count == 3:
            mute_time = 5
        elif warn_count == 6:
            mute_time = 10

        if mute_time:
            try:
                await client.restrict_chat_member(
                    message.chat.id,
                    message.reply_to_message.from_user.id,
                    ChatPermissions(),
                    until_date=datetime.utcnow() + timedelta(minutes=mute_time)
                )
                await message.reply(f"🔇 User auto-muted for {mute_time} minutes due to warnings.")
            except Exception as e:
                await message.reply(f"Failed to mute: {e}")

    @app.on_message(filters.command("resetwarns") & filters.group)
    async def reset_warns(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to reset warnings.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to reset their warns!")
        user_id = str(message.reply_to_message.from_user.id)
        warnings = load_warnings()
        group_id = str(message.chat.id)
        if group_id in warnings and user_id in warnings[group_id]:
            warnings[group_id][user_id] = 0
            save_warnings(warnings)
            await message.reply("Warns reset!")
        else:
            await message.reply("User has no warns.")

    @app.on_message(filters.command("warns") & filters.group)
    async def check_warns(client, message: Message):
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to check their warns!")
        user_id = str(message.reply_to_message.from_user.id)
        warnings = load_warnings()
        group_id = str(message.chat.id)
        count = warnings.get(group_id, {}).get(user_id, 0)
        await message.reply(f"{message.reply_to_message.from_user.mention} has {count} warns.")

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to mute users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to mute them!")
        try:
            args = message.text.split()
            if len(args) > 1:
                mute_time = int(args[1])
            else:
                mute_time = 0  # Indefinite
        except Exception:
            mute_time = 0
        try:
            if mute_time:
                until = datetime.utcnow() + timedelta(minutes=mute_time)
            else:
                until = None
            await client.restrict_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id,
                ChatPermissions(),
                until_date=until
            )
            await message.reply(f"🔇 User muted{' for ' + str(mute_time) + ' minutes' if mute_time else ' indefinitely'}!")
        except Exception as e:
            await message.reply(f"Failed to mute: {e}")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to unmute users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to unmute them!")
        try:
            await client.restrict_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                )
            )
            await message.reply("User unmuted!")
        except Exception as e:
            await message.reply(f"Failed to unmute: {e}")

    @app.on_message(filters.command("flirtywarn") & filters.group)
    async def flirty_warn(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to flirty-warn users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to give a flirty warning!")
        user = message.reply_to_message.from_user
        flirty_msgs = [
            f"🍑 {user.mention}, you’re being naughty… Keep it up and you might get spanked 😉",
            f"😈 {user.mention}, the succubi have their eyes on you! Behave… or don’t.",
            f"💋 {user.mention}, you’ve earned a flirty warning. Tread carefully… or maybe don’t!",
            f"🔥 {user.mention}, this is your official flirty warning… Things are getting steamy.",
            f"😉 {user.mention}, a flirty warning just for you. Want to see what happens at 3?",
            f"👠 {user.mention}, the more flirty warns you collect, the naughtier you look to us…"
        ]
        import random
        await message.reply(random.choice(flirty_msgs))

    # Add /ban and /unban commands if needed
    @app.on_message(filters.command("ban") & filters.group)
    async def ban_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to ban users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to ban them!")
        try:
            await client.kick_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id
            )
            await message.reply("User banned from group!")
        except Exception as e:
            await message.reply(f"Failed to ban: {e}")

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to unban users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to unban them!")
        try:
            await client.unban_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id
            )
            await message.reply("User unbanned from group!")
        except Exception as e:
            await message.reply(f"Failed to unban: {e}")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to kick users.")
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to kick them!")
        try:
            await client.kick_chat_member(
                message.chat.id,
                message.reply_to_message.from_user.id
            )
            await message.reply("User kicked from group!")
        except Exception as e:
            await message.reply(f"Failed to kick: {e}")

