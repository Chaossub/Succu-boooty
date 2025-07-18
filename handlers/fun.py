import random
from pyrogram import filters
from pyrogram.types import Message

def register(app):
    from handlers.xp import add_xp, get_leaderboard  # Both are normal (not async)

    @app.on_message(filters.command("bite") & filters.group)
    async def bite(client, message: Message):
        user = message.from_user
        gain = random.randint(1, 5)
        add_xp(message.chat.id, user.id, gain)   # <-- NO await!
        await message.reply(f"{user.mention} bites back! +{gain} XP")

    @app.on_message(filters.command("spank") & filters.group)
    async def spank(client, message: Message):
        user = message.from_user
        gain = random.randint(1, 5)
        add_xp(message.chat.id, user.id, gain)
        await message.reply(f"{user.mention} gets spanked! +{gain} XP")

    @app.on_message(filters.command("tease") & filters.group)
    async def tease(client, message: Message):
        user = message.from_user
        gain = random.randint(1, 5)
        add_xp(message.chat.id, user.id, gain)
        await message.reply(f"{user.mention} teased! +{gain} XP")

    @app.on_message(filters.command("naughtystats") & filters.group)
    async def naughtystats(client, message: Message):
        board = get_leaderboard(message.chat.id)
        if not board:
            return await message.reply("No stats recorded yet.")
        lines = ["📊 Naughty XP Stats:"]
        for i, doc in enumerate(board, start=1):
            uid = doc["user_id"]
            xp = doc["xp"]
            lines.append(f"{i}. <a href='tg://user?id={uid}'>User</a> — {xp} XP")
        await message.reply("\n".join(lines), disable_web_page_preview=True)
