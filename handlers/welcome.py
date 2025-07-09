from pyrogram import Client, filters
from pyrogram.types import ChatMemberUpdated
import random

# ─── Welcome and Goodbye Messages ─────────────────────────────────────────────

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

# ─── Handlers ─────────────────────────────────────────────────────────────────

async def welcome_handler(client: Client, member: ChatMemberUpdated):
    if member.new_chat_member.user.is_bot:
        return

    new_status = getattr(member, "new_chat_member", None)
    old_status = getattr(member, "old_chat_member", None)

    if new_status and getattr(new_status, "status", None) in ("member", "restricted"):
        mention = member.new_chat_member.user.mention
        message = random.choice(flirty_welcome_messages).format(mention=mention)
        await client.send_message(member.chat.id, message)

async def goodbye_handler(client: Client, member: ChatMemberUpdated):
    new_status = getattr(member, "new_chat_member", None)
    old_status = getattr(member, "old_chat_member", None)

    if (
        getattr(old_status, "status", None) in ("member", "restricted")
        and getattr(new_status, "status", None) in ("left", "kicked", "banned")
    ):
        mention = member.old_chat_member.user.mention
        message = random.choice(flirty_goodbye_messages).format(mention=mention)
        await client.send_message(member.chat.id, message)

# ─── Register ─────────────────────────────────────────────────────────────────

def register(app: Client):
    app.on_chat_member_updated()(welcome_handler)
    app.on_chat_member_updated()(goodbye_handler)

