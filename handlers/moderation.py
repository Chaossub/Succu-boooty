import logging
import random
import asyncio
import datetime
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions
from pymongo import MongoClient
import os

# Monkey-patch workaround for Pyrogram 2.0.106 "to_bytes" bug:
from pyrogram.raw.types.chat_banned_rights import ChatBannedRights
_orig_cbr_write = ChatBannedRights.write
def _patched_cbr_write(self, *args, **kwargs):
    if not getattr(self, "until_date", None):
        self.until_date = 2147483647
    return _orig_cbr_write(self, *args, **kwargs)
ChatBannedRights.write = _patched_cbr_write

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
)

OWNER_ID = 6964994611

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
warns = db["warns"]

FLIRTY_WARN_MESSAGES = [
    "Oh naughty! {mention}, that’s a little spicy for the Sanctuary 😉",
    "{mention}, watch out! The succubi are watching your every move 😈",
    "Careful, {mention}… temptation isn’t always kind 😘",
    "Flirty warning for {mention}! Time to behave… or not 😜",
    "{mention}, you’re treading on thin ice… but we like it 🔥"
]

def is_admin(chat_member, user_id):
    """Check if user is an admin or the hardwired owner."""
    return user_id == OWNER_ID or (chat_member and chat_member.status in ("administrator", "creator"))

def get_warn_count(chat_id, user_id):
    record = warns.find_one({"chat_id": chat_id, "user_id": user_id})
    return record["count"] if record else 0

def set_warn_count(chat_id, user_id, count):
    warns.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"count": count}},
        upsert=True,
    )

def reset_warns(chat_id, user_id):
    warns.delete_one({"chat_id": chat_id, "user_id": user_id})

def mute_time(warn_count):
    if warn_count == 3:
        return 5 * 60   # 5 min
    if warn_count == 6:
        return 10 * 60  # 10 min
    return 0

async def mute_user(app, chat_id, user_id, duration):
    until = int((datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)).timestamp())
    await app.restrict_chat_member(
        chat_id,
        user_id,
        permissions=ChatPermissions(),
        until_date=until
    )

async def unmute_user(app, chat_id, user_id):
    await app.restrict_chat_member(
        chat_id,
        user_id,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
        ),
        until_date=None
    )

async def get_user(client, chat_id, identifier):
    """Resolve @username or ID to a User object."""
    try:
        if identifier.isdigit():
            member = await client.get_chat_member(chat_id, int(identifier))
            return member.user
        if identifier.startswith("@"):
            member = await client.get_chat_member(chat_id, identifier)
            return member.user
    except Exception:
        pass
    try:
        return await client.get_users(identifier)
    except Exception:
        return None

async def resolve_target(client, message: Message):
    """Get target user from reply or argument."""
    if message.reply_to_message:
        return message.reply_to_message.from_user
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("📢 Reply to someone or specify @username/ID.")
        return None
    user = await get_user(client, message.chat.id, parts[1].strip())
    if not user:
        await message.reply("❌ Could not find that user.")
    return user

def register(app):

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can warn.")
        user = await resolve_target(client, message)
        if not user:
            return
        if user.is_bot or user.id == OWNER_ID:
            return await message.reply("❌ Cannot warn that user.")
        count = get_warn_count(message.chat.id, user.id) + 1
        set_warn_count(message.chat.id, user.id, count)
        await message.reply(f"{user.mention} has been warned. 😉\nTotal warns: <b>{count}</b>.")
        mute_seconds = mute_time(count)
        if mute_seconds:
            await mute_user(client, message.chat.id, user.id, mute_seconds)
            await message.reply(f"{user.mention} has been auto-muted for {mute_seconds//60} minutes for repeated warnings!")

            async def auto_unmute():
                await asyncio.sleep(mute_seconds)
                await unmute_user(client, message.chat.id, user.id)
                await client.send_message(message.chat.id, f"{user.mention} has been automatically unmuted.")

            asyncio.create_task(auto_unmute())

    @app.on_message(filters.command("resetwarns") & filters.group)
    async def resetwarns_handler(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can reset warns.")
        user = await resolve_target(client, message)
        if not user:
            return
        reset_warns(message.chat.id, user.id)
        await message.reply(f"{user.mention}'s warnings have been reset!")

    @app.on_message(filters.command("warns") & filters.group)
    async def warns_count_handler(client, message: Message):
        user = await resolve_target(client, message) if message.reply_to_message or len(message.text.split()) > 1 else message.from_user
        count = get_warn_count(message.chat.id, user.id)
        await message.reply(f"{user.mention} has <b>{count}</b> warning(s).")

    @app.on_message(filters.command("flirtywarn") & filters.group)
    async def flirty_warn(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can flirty-warn.")
        user = await resolve_target(client, message)
        if not user:
            return
        text = random.choice(FLIRTY_WARN_MESSAGES).format(mention=user.mention)
        await message.reply(text)

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user_cmd(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can mute.")
        user = await resolve_target(client, message)
        if not user:
            return
        if user.is_bot or user.id == OWNER_ID or user.id == message.from_user.id:
            return await message.reply("❌ Cannot mute that user.")
        perms = ChatPermissions()
        await client.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=perms,
            until_date=None
        )
        await message.reply(f"{user.mention} has been muted indefinitely.")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user_cmd(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can unmute.")
        user = await resolve_target(client, message)
        if not user:
            return
        await unmute_user(client, message.chat.id, user.id)
        await message.reply(f"{user.mention} has been unmuted.")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can kick.")
        user = await resolve_target(client, message)
        if not user:
            return
        await client.ban_chat_member(message.chat.id, user.id, until_date=None)
        await client.unban_chat_member(message.chat.id, user.id)
        await message.reply(f"{user.mention} has been kicked from the group.")

    @app.on_message(filters.command("ban") & filters.group)
    async def ban_user(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can ban.")
        user = await resolve_target(client, message)
        if not user:
            return
        await client.ban_chat_member(message.chat.id, user.id, until_date=None)
        await message.reply(f"{user.mention} has been banned from the group.")

    @app.on_message(filters.command("unban") & filters.group)
    async def unban_user(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can unban.")
        user = await resolve_target(client, message)
        if not user:
            return
        await client.unban_chat_member(message.chat.id, user.id)
        await message.reply(f"{user.mention} has been unbanned from the group.")

    @app.on_message(filters.command("userinfo") & filters.group)
    async def userinfo(client, message: Message):
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can use /userinfo.")
        user = await resolve_target(client, message)
        if not user:
            return
        info = await client.get_chat_member(message.chat.id, user.id)
        text = (
            f"<b>User Info:</b>\n"
            f"Name: {user.mention}\n"
            f"ID: <code>{user.id}</code>\n"
            f"Status: {info.status}\n"
        )
        await message.reply(text)
