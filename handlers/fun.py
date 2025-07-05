import json
import random
from pyrogram import filters
from pyrogram.types import Message

XP_PATH = "data/xp.json"

def load_xp():
    with open(XP_PATH, "r") as f:
        return json.load(f)

def save_xp(data):
    with open(XP_PATH, "w") as f:
        json.dump(data, f)

def add_xp(chat_id, user_id, amount):
    chat_id = str(chat_id)
    user_id = str(user_id)
    data = load_xp()
    if chat_id not in data:
        data[chat_id] = {}
    if user_id not in data[chat_id]:
        data[chat_id][user_id] = 0
    data[chat_id][user_id] += amount
    save_xp(data)
    return data[chat_id][user_id]

def get_xp(chat_id, user_id):
    data = load_xp()
    return data.get(str(chat_id), {}).get(str(user_id), 0)

def get_leaderboard(chat_id, top=10):
    data = load_xp()
    chat_data = data.get(str(chat_id), {})
    sorted_users = sorted(chat_data.items(), key=lambda x: x[1], reverse=True)
    return sorted_users[:top]

def register(app):

    @app.on_message(filters.command("bite") & filters.group)
    async def bite(_, message: Message):
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to bite them!")
        user = message.reply_to_message.from_user
        xp = add_xp(message.chat.id, user.id, 3)
        responses = [
            f"😈 *chomp!* {user.mention} just got a playful bite! (+3 naughty XP)",
            f"🦷 {user.mention}, hope you liked that little nibble… (+3 naughty XP)",
            f"🔥 Succubus bite attack! {user.mention} is looking naughtier now. (+3 XP)",
            f"💋 A naughty bite for {user.mention}! Naughty meter rises… (+3 XP)"
        ]
        await message.reply(random.choice(responses))

    @app.on_message(filters.command("spank") & filters.group)
    async def spank(_, message: Message):
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to spank them!")
        user = message.reply_to_message.from_user
        xp = add_xp(message.chat.id, user.id, 2)
        responses = [
            f"🍑 Spank! {user.mention} just got a smack on the booty. (+2 XP)",
            f"👏 Naughty! {user.mention} got a good spanking. (+2 XP)",
            f"😳 Oof! {user.mention}, you’re definitely on the naughty list now. (+2 XP)",
            f"🔥 That’s a spicy spank for {user.mention}! (+2 naughty XP)"
        ]
        await message.reply(random.choice(responses))

    @app.on_message(filters.command("tease") & filters.group)
    async def tease(_, message: Message):
        if not message.reply_to_message:
            return await message.reply("Reply to a user's message to tease them!")
        user = message.reply_to_message.from_user
        xp = add_xp(message.chat.id, user.id, 1)
        responses = [
            f"😉 Tease alert! {user.mention} can barely handle it. (+1 XP)",
            f"😈 {user.mention} just got playfully teased. (+1 XP)",
            f"💋 {user.mention}, someone’s feeling mischievous! (+1 naughty XP)",
            f"😏 {user.mention} — that was a very flirty tease! (+1 XP)"
        ]
        await message.reply(random.choice(responses))

    @app.on_message(filters.command("naughty") & filters.group)
    async def naughty_meter(_, message: Message):
        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            user = message.from_user
        xp = get_xp(message.chat.id, user.id)
        await message.reply(
            f"{user.mention}, your naughty meter: <b>{xp}</b> XP!"
        )

    @app.on_message(filters.command("leaderboard") & filters.group)
    async def leaderboard(_, message: Message):
        leaderboard = get_leaderboard(message.chat.id, top=10)
        if not leaderboard:
            return await message.reply("No naughty XP tracked yet!")
        text = "🏆 <b>Naughtiest Members</b> 🏆\n"
        for i, (uid, xp) in enumerate(leaderboard, 1):
            mention = f"<a href='tg://user?id={uid}'>User</a>"
            text += f"{i}. {mention} — <b>{xp}</b> XP\n"
        await message.reply(text)
