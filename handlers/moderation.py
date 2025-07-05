import logging
import random
from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

# ─── Monkey-patch to avoid the NoneType.to_bytes bug in Pyrogram 2.0.106 ───
from pyrogram.raw.types.chat_banned_rights import ChatBannedRights

_orig_cbr_write = ChatBannedRights.write
def _patched_cbr_write(self, *args, **kwargs):
    # If until_date is falsy or None, force it to the 32-bit max timestamp
    if not getattr(self, "until_date", None):
        self.until_date = 2147483647
    return _orig_cbr_write(self, *args, **kwargs)

ChatBannedRights.write = _patched_cbr_write
# ────────────────────────────────────────────────────────────────────────────

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
    return user_id == OWNER_ID or (chat_member and chat_member.status in ("administrator", "creator"))

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
        logging.debug("‹WARN› from %s in %s", message.from_user.id, message.chat.id)
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can warn.")
        user = await resolve_target(client, message)
        if not user:
            return
        await message.reply(f"{user.mention} has been warned. 😉")

    @app.on_message(filters.command("flirtywarn") & filters.group)
    async def flirty_warn(client, message: Message):
        logging.debug("‹FLIRTYWARN› from %s in %s", message.from_user.id, message.chat.id)
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can flirty-warn.")
        user = await resolve_target(client, message)
        if not user:
            return
        text = random.choice(FLIRTY_WARN_MESSAGES).format(mention=user.mention)
        await message.reply(text)

    @app.on_message(filters.command("mute") & filters.group)
    async def mute_user(client, message: Message):
        logging.info("‹MUTE› %s in %s", message.from_user.id, message.chat.id)
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can mute.")
        user = await resolve_target(client, message)
        if not user:
            return
        if user.is_bot or user.id == OWNER_ID or user.id == message.from_user.id:
            return await message.reply("❌ Cannot mute that user.")
        perms = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        logging.debug("Restricting %s indefinitely", user.id)
        await client.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=perms,
            until_date=None  # patched above to become 2147483647
        )
        await message.reply(f"{user.mention} has been muted indefinitely.")

    @app.on_message(filters.command("unmute") & filters.group)
    async def unmute_user(client, message: Message):
        logging.info("‹UNMUTE› %s in %s", message.from_user.id, message.chat.id)
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can unmute.")
        user = await resolve_target(client, message)
        if not user:
            return
        perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
        )
        logging.debug("Lifting restrictions for %s", user.id)
        await client.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=perms,
            until_date=None
        )
        await message.reply(f"{user.mention} has been unmuted.")

    @app.on_message(filters.command("kick") & filters.group)
    async def kick_user(client, message: Message):
        logging.info("‹KICK› %s in %s", message.from_user.id, message.chat.id)
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
        logging.info("‹BAN› %s in %s", message.from_user.id, message.chat.id)
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
        logging.info("‹UNBAN› %s in %s", message.from_user.id, message.chat.id)
        cm = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(cm, message.from_user.id):
            return await message.reply("❌ Only admins can unban.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].isdigit():
            return await message.reply("Usage: /unban <user_id>")
        user_id = int(parts[1])
        await client.unban_chat_member(message.chat.id, user_id)
        await message.reply(f"User <code>{user_id}</code> has been unbanned.")

    @app.on_message(filters.command("userinfo") & filters.group)
    async def userinfo(client, message: Message):
        logging.info("‹USERINFO› %s in %s", message.from_user.id, message.chat.id)
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
