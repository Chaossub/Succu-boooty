import random
from pyrogram import filters
from pyrogram.types import Message
from handlers import xp  # Import XP helper

def register(app):

    BITE_MESSAGES = [
        "{} bites you gently with a sly smile. 💋",
        "{} gives a playful nibble! 😘",
        "{} sinks their teeth in just enough to tease. 😈",
        "{} bites softly, leaving you wanting more. 🧛‍♀️",
        "{} playfully bites your shoulder! 😏"
    ]

    SPANK_MESSAGES = [
        "{} delivers a cheeky spank! 🍑",
        "{} playfully spanks you with a grin. 😜",
        "{} spanks with a little extra sass! 🔥",
        "{} gives a loving spank, making you blush. 😊",
        "{} smacks your behind, teasingly! 😉"
    ]

    TEASE_MESSAGES = [
        "{} teases you with a wicked smile. 😈",
        "{} flutters lashes and teases mercilessly. 💃",
        "{} blows a kiss and teases you playfully. 😘",
        "{} wiggles fingers and teases you senseless. 😜",
        "{} gives a flirty wink and teases you. 😉"
    ]

    @app.on_message(filters.command("bite") & filters.group)
    async def bite(client, message: Message):
        user = message.from_user
        if not user:
            return
        xp.add_xp(message.chat.id, user.id, 5)
        text = random.choice(BITE_MESSAGES).format(user.mention)
        total_xp = xp.get_xp(message.chat.id, user.id)
        await message.reply(f"{text}\n\nGained 5 naughty XP! Total: <b>{total_xp}</b> XP.")

    @app.on_message(filters.command("spank") & filters.group)
    async def spank(client, message: Message):
        user = message.from_user
        if not user:
            return
        xp.add_xp(message.chat.id, user.id, 5)
        text = random.choice(SPANK_MESSAGES).format(user.mention)
        total_xp = xp.get_xp(message.chat.id, user.id)
        await message.reply(f"{text}\n\nGained 5 naughty XP! Total: <b>{total_xp}</b> XP.")

    @app.on_message(filters.command("tease") & filters.group)
    async def tease(client, message: Message):
        user = message.from_user
        if not user:
            return
        xp.add_xp(message.chat.id, user.id, 5)
        text = random.choice(TEASE_MESSAGES).format(user.mention)
        total_xp = xp.get_xp(message.chat.id, user.id)
        await message.reply(f"{text}\n\nGained 5 naughty XP! Total: <b>{total_xp}</b> XP.")
