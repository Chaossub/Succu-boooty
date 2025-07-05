import json
import random
from pyrogram import filters
from pyrogram.types import Message

SUMMON_PATH = "data/summon.json"
SUPER_ADMIN_ID = 6964994611

def load_summon():
    with open(SUMMON_PATH, "r") as f:
        return json.load(f)

def save_summon(data):
    with open(SUMMON_PATH, "w") as f:
        json.dump(data, f)

def is_admin(app, user_id, chat_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = app.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

def add_user_to_tracking(chat_id, user_id):
    chat_id = str(chat_id)
    user_id = str(user_id)
    data = load_summon()
    if chat_id not in data:
        data[chat_id] = []
    if user_id not in data[chat_id]:
        data[chat_id].append(user_id)
        save_summon(data)

def register(app):

    @app.on_message(filters.command("trackall") & filters.group)
    async def track_all(client, message: Message):
        if not is_admin(client, message.from_user.id, message.chat.id):
            return await message.reply("You need to be an admin to use /trackall.")
        members = []
        async for member in client.get_chat_members(message.chat.id):
            if not member.user.is_bot:
                add_user_to_tracking(message.chat.id, member.user.id)
                members.append(member.user.mention)
        await message.reply(f"Tracked all members!\nTotal tracked: {len(members)}")

    @app.on_message(filters.command("summon") & filters.group)
    async def summon(client, message: Message):
        args = message.text.split(maxsplit=1)
        data = load_summon()
        chat_id = str(message.chat.id)
        # summon specific user
        if len(args) > 1 and args[1].startswith("@"):
            try:
                user = await client.get_users(args[1].strip())
                add_user_to_tracking(message.chat.id, user.id)
                await message.reply(f"{user.mention}, you are being summoned!")
            except Exception:
                await message.reply("Could not find that user.")
            return
        # summon all tracked
        tracked = data.get(chat_id, [])
        if not tracked:
            return await message.reply("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            mentions.append(f"<a href='tg://user?id={uid}'>User</a>")
        text = "Summoning everyone!\n" + " ".join(mentions)
        await message.reply(text)

    @app.on_message(filters.command("flirtysummon") & filters.group)
    async def flirty_summon(client, message: Message):
        args = message.text.split(maxsplit=1)
        data = load_summon()
        chat_id = str(message.chat.id)
        flirty_lines = [
            "😈 Come out and play!",
            "💋 The succubi are calling…",
            "🔥 Someone wants your attention!",
            "👠 It’s getting steamy in here!"
        ]
        # flirty summon specific user
        if len(args) > 1 and args[1].startswith("@"):
            try:
                user = await client.get_users(args[1].strip())
                add_user_to_tracking(message.chat.id, user.id)
                msg = f"{user.mention}, {random.choice(flirty_lines)}"
                await message.reply(msg)
            except Exception:
                await message.reply("Could not find that user.")
            return
        # flirty summon all tracked
        tracked = data.get(chat_id, [])
        if not tracked:
            return await message.reply("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            mentions.append(f"<a href='tg://user?id={uid}'>User</a>")
        text = random.choice(flirty_lines) + "\n" + " ".join(mentions)
        await message.reply(text)

    @app.on_message(filters.command("summonall") & filters.group)
    async def summon_all(client, message: Message):
        data = load_summon()
        chat_id = str(message.chat.id)
        tracked = data.get(chat_id, [])
        if not tracked:
            return await message.reply("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            mentions.append(f"<a href='tg://user?id={uid}'>User</a>")
        text = "Summoning everyone!\n" + " ".join(mentions)
        await message.reply(text)

    @app.on_message(filters.command("flirtysummonall") & filters.group)
    async def flirty_summon_all(client, message: Message):
        data = load_summon()
        chat_id = str(message.chat.id)
        flirty_lines = [
            "😈 Come out and play, naughty ones!",
            "💋 The succubi want *everyone*…",
            "🔥 All the hotties assemble!",
            "👠 Who’s feeling naughty tonight?"
        ]
        tracked = data.get(chat_id, [])
        if not tracked:
            return await message.reply("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            mentions.append(f"<a href='tg://user?id={uid}'>User</a>")
        text = random.choice(flirty_lines) + "\n" + " ".join(mentions)
        await message.reply(text)
