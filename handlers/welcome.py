from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated
import random

flirty_welcome_messages = [
    "💋 Welcome to the Sanctuary, {mention}... We've been expecting you~",
    "🔥 Well hello there, {mention}... Ready to sin a little?",
    "👠 {mention} just stepped into temptation. Don't be shy~",
    "😈 {mention}, welcome! Let’s see how naughty you can get.",
    "💄 Look who wandered in... Welcome, {mention}~",
    "🌹 {mention}, the Succubi were whispering about you... welcome.",
    "💫 {mention}, you’re now part of the most sinful little club on Telegram~",
]

flirty_goodbye_messages = [
    "💔 {mention} couldn’t handle the heat...",
    "👋 {mention} took their halo and ran away~",
    "😈 One less soul to tease... goodbye, {mention}.",
    "🌙 {mention} has left the pleasure palace.",
    "🥀 {mention} faded into the night... how sad.",
]

def is_join(event: ChatMemberUpdated):
    """Detects member joined (not promoted/demoted)."""
    return (
        event.old_chat_member.status in ("left", "kicked")
        and event.new_chat_member.status in ("member", "restricted")
        and not event.new_chat_member.user.is_bot
    )

def is_leave(event: ChatMemberUpdated):
    """Detects member left (not demoted)."""
    return (
        event.old_chat_member.status in ("member", "restricted")
        and event.new_chat_member.status in ("left", "kicked", "banned")
        and not event.old_chat_member.user.is_bot
    )

async def welcome_goodbye_handler(client: Client, event: ChatMemberUpdated):
    if is_join(event):
        mention = event.new_chat_member.user.mention
        msg = random.choice(flirty_welcome_messages).format(mention=mention)
        await client.send_message(event.chat.id, msg)
    elif is_leave(event):
        mention = event.old_chat_member.user.mention
        msg = random.choice(flirty_goodbye_messages).format(mention=mention)
        await client.send_message(event.chat.id, msg)
    # else: ignore admin changes, bans, bot joins, etc.

def register(app: Client):
    app.on_chat_member_updated()(welcome_goodbye_handler)
