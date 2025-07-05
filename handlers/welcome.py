import random
from pyrogram import filters
from pyrogram.types import Message, ChatMemberUpdated

def register(app):

    WELCOMES = [
        "🔥 Welcome to the Succubus Sanctuary, {mention}! Temptation lives here. 😈",
        "💋 {mention}, you've entered where naughty is the norm. Have fun!",
        "👠 {mention}, the succubi are watching... be as sinful as you dare.",
        "😈 Welcome, {mention}! May your stay be as indulgent as you want.",
        "✨ {mention}, step into our world of sin and surprises!"
    ]

    GOODBYES = [
        "👋 {mention} has left the Sanctuary... hope you had your fill of temptation!",
        "💨 {mention} escaped the succubi’s clutches... for now!",
        "😏 {mention} slipped away, but the fun goes on!",
        "💔 {mention} is gone! The Sanctuary is one naughty soul lighter."
    ]

    @app.on_message(filters.new_chat_members)
    async def welcome_new_member(client, message: Message):
        for user in message.new_chat_members:
            mention = user.mention
            msg = random.choice(WELCOMES).format(mention=mention)
            await message.reply(msg)

    @app.on_chat_member_updated()
    async def goodbye_handler(client, update: ChatMemberUpdated):
        old = update.old_chat_member
        new = update.new_chat_member
        user = update.new_chat_member.user

        # User left or was kicked/banned
        if old.status in ("member", "restricted") and new.status in ("left", "kicked"):
            mention = user.mention if user else "A user"
            msg = random.choice(GOODBYES).format(mention=mention)
            try:
                await client.send_message(update.chat.id, msg)
            except Exception as e:
                print(f"Failed to send goodbye: {e}")

