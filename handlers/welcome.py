import random
from pyrogram import filters
from pyrogram.types import Message

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

    @app.on_message(filters.left_chat_member)
    async def goodbye_member(client, message: Message):
        user = message.left_chat_member
        mention = user.mention
        msg = random.choice(GOODBYES).format(mention=mention)
        await message.reply(msg)
