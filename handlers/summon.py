import os
import json
import random

from pyrogram import filters
from pyrogram.types import Message

# ─── Config ────────────────────────────────────────────────────────────
SUMMON_PATH    = "data/summon.json"
SUPER_ADMIN_ID = 6964994611
# ────────────────────────────────────────────────────────────────────────

def load_summon():
    if not os.path.exists(SUMMON_PATH):
        return {}
    with open(SUMMON_PATH, "r") as f:
        return json.load(f)

def save_summon(data):
    os.makedirs(os.path.dirname(SUMMON_PATH), exist_ok=True)
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
        count = 0
        async for m in client.get_chat_members(message.chat.id):
            if not m.user.is_bot:
                add_user_to_tracking(message.chat.id, m.user.id)
                count += 1
        await message.reply_text(
            f"✅ Tracked all members!\nTotal tracked: {count}",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("summon") & filters.group)
    async def summon_one(client, message: Message):
        # 1) If the command is a reply, grab that user:
        if message.reply_to_message:
            target = message.reply_to_message.from_user
        else:
            # 2) Otherwise expect “/summon @username”
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].startswith("@"):
                return await message.reply_text(
                    "Usage:\n"
                    "• Reply to someone’s message with /summon\n"
                    "• Or /summon @username"
                )
            username = parts[1].lstrip("@")
            try:
                target = await client.get_users(username)
            except Exception:
                return await message.reply_text("❌ Could not find that username.")

        # 3) Verify they’re in the chat
        try:
            await client.get_chat_member(message.chat.id, target.id)
        except Exception:
            return await message.reply_text("❌ That user is not in this group.")

        # 4) Track & mention
        add_user_to_tracking(message.chat.id, target.id)
        await message.reply_text(
            f"{target.mention}, you are being summoned!",
            parse_mode="html"
        )

    @app.on_message(filters.command("summonall") & filters.group)
    async def summon_all(client, message: Message):
        data = load_summon().get(str(message.chat.id), [])
        if not data:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in data:
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
        # single‐target
        if message.reply_to_message or (len(message.text.split()) > 1 and message.text.split()[1].startswith("@")):
            # reuse the same logic as /summon
            # pretend this is a mini-summon
            return await summon_one(client, message)

        # otherwise summon all
        data = load_summon().get(str(message.chat.id), [])
        if not data:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in data:
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
        flirty = [
            "😈 Come out and play, naughty ones!",
            "💋 The succubi want *everyone*…",
            "🔥 All the hotties assemble!",
            "👠 Who’s feeling naughty tonight?"
        ]
        data = load_summon().get(str(message.chat.id), [])
        if not data:
            return await message.reply_text("No tracked users! Use /trackall first.")
        mentions = []
        for uid in data:
            try:
                user = await client.get_users(int(uid))
                mentions.append(user.mention)
            except:
                continue
        await message.reply_text(
            random.choice(flirty) + "\n" + " ".join(mentions),
            parse_mode="html",
            disable_web_page_preview=True
        )

    @app.on_message(filters.command("cancel") & filters.group)
    async def cancel_setup(client, message: Message):
        await message.reply_text("🚫 Federation setup canceled.")

    @app.on_message(filters.command("help") & filters.group)
    async def help_cmd(client, message: Message):
        cmds = [
            "/trackall — track everyone",
            "/summon @username or reply — summon one",
            "/summonall — summon all",
            "/flirtysummon @username or reply — flirty one",
            "/flirtysummonall — flirty all",
            "/cancel — cancel setup"
        ]
        await message.reply_text(
            "📜 Available commands:\n" + "\n".join(cmds),
            disable_web_page_preview=True
        )
