import os
import json
import random

from pyrogram import filters
from pyrogram.types import Message, ChatPermissions

# Path where tracked IDs are saved
SUMMON_PATH = "data/summon.json"
SUPER_ADMIN_ID = 6964994611

def load_summon():
    if not os.path.exists(SUMMON_PATH):
        return {}
    with open(SUMMON_PATH, "r") as f:
        return json.load(f)

def save_summon(data):
    with open(SUMMON_PATH, "w") as f:
        json.dump(data, f)

def add_user_to_tracking(chat_id: int, user_id: int):
    data = load_summon()
    key = str(chat_id)
    if key not in data:
        data[key] = []
    if user_id not in data[key]:
        data[key].append(user_id)
        save_summon(data)

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def register(app):

    @app.on_message(filters.command("trackall") & filters.group)
    async def track_all(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You need to be an admin to use /trackall.")
        members = []
        async for member in client.get_chat_members(message.chat.id):
            if not member.user.is_bot:
                add_user_to_tracking(message.chat.id, member.user.id)
                members.append(member.user.mention)
        await message.reply_text(
            f"✅ Tracked all members!\nTotal tracked: {len(members)}",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("summon") & filters.group)
    async def summon_one(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].startswith("@"):
            return await message.reply_text("Usage: /summon @username")
        username = args[1].strip()
        try:
            user = await client.get_users(username)
            add_user_to_tracking(message.chat.id, user.id)
            await message.reply_text(
                f"{user.mention}, you are being summoned!",
                parse_mode="html"
            )
        except:
            await message.reply_text("❌ Could not find that user.")

    @app.on_message(filters.command("summonall") & filters.group)
    async def summon_all(client, message: Message):
        data = load_summon()
        tracked = data.get(str(message.chat.id), [])
        if not tracked:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            try:
                user = await client.get_users(int(uid))
                mentions.append(user.mention)
            except:
                continue
        await message.reply_text(
            "🔔 Summoning everyone!\n" + " ".join(mentions),
            parse_mode="html",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("flirtysummon") & filters.group)
    async def flirty_summon(client, message: Message):
        flirty_lines = [
            "😈 Come out and play!",
            "💋 The succubi are calling…",
            "🔥 Someone wants your attention!",
            "👠 It’s getting steamy in here!"
        ]
        args = message.text.split(maxsplit=1)
        # specific
        if len(args) > 1 and args[1].startswith("@"):
            try:
                user = await client.get_users(args[1].strip())
                add_user_to_tracking(message.chat.id, user.id)
                await message.reply_text(
                    f"{user.mention}, {random.choice(flirty_lines)}",
                    parse_mode="html"
                )
            except:
                await message.reply_text("❌ Could not find that user.")
            return
        # all
        data = load_summon()
        tracked = data.get(str(message.chat.id), [])
        if not tracked:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            try:
                user = await client.get_users(int(uid))
                mentions.append(user.mention)
            except:
                continue
        await message.reply_text(
            random.choice(flirty_lines) + "\n" + " ".join(mentions),
            parse_mode="html",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("flirtysummonall") & filters.group)
    async def flirty_summon_all(client, message: Message):
        flirty_lines = [
            "😈 Come out and play, naughty ones!",
            "💋 The succubi want *everyone*…",
            "🔥 All the hotties assemble!",
            "👠 Who’s feeling naughty tonight?"
        ]
        data = load_summon()
        tracked = data.get(str(message.chat.id), [])
        if not tracked:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in tracked:
            try:
                user = await client.get_users(int(uid))
                mentions.append(user.mention)
            except:
                continue
        await message.reply_text(
            random.choice(flirty_lines) + "\n" + " ".join(mentions),
            parse_mode="html",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("cancel") & filters.group)
    async def cancel_federation_setup(client, message: Message):
        # placeholder: implement your multi-step federation state cleanup here
        await message.reply_text("🚫 Federation setup canceled.")

    @app.on_message(filters.command("help") & filters.group)
    async def help_cmd(client, message: Message):
        # you can list only the commands users may use
        commands = [
            "/trackall — track everyone",
            "/summon @username — summon one",
            "/summonall — summon all tracked",
            "/flirtysummon — flirty version",
            "/flirtysummonall — flirty all",
            "/cancel — cancel federation setup"
        ]
        await message.reply_text("📜 Available commands:\n" + "\n".join(commands))

