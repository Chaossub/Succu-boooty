import random
from pyrogram import filters
from pyrogram.types import Message

WELCOME_MESSAGES = [
    "🔥 Welcome to the Succubus Sanctuary, {mention}! Temptation lives here. 😈",
    "💋 {mention}, you've entered where naughty is the norm. Have fun!",
    "👠 {mention}, the succubi are watching... be as sinful as you dare.",
    "😈 Welcome, {mention}! May your stay be as indulgent as you want.",
    "✨ {mention}, step into our world of sin and surprises!"
]

def register(app):

    @app.on_message(filters.new_chat_members)
    async def welcome_new_member(client, message: Message):
        for user in message.new_chat_members:
            mention = user.mention
            text = random.choice(WELCOME_MESSAGES).format(mention=mention)
            await message.reply(text)


