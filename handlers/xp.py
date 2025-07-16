import os
import random
import logging
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message, User

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise RuntimeError("Please set MONGO_URI or MONGODB_URI in your environment")

DB_NAME = os.getenv("MONGO_DB", "succubot")

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
xp_collection = db["xp"]

OWNER_ID = 6964994611

def add_xp(chat_id: int, user_id: int, amount: int):
    xp_collection.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$inc": {"xp": amount}},
        upsert=True
    )

def get_leaderboard(chat_id: int, limit: int = 10):
    return list(
        xp_collection
        .find({"chat_id": chat_id})
        .sort("xp", -1)
        .limit(limit)
    )

def reset_xp(chat_id: int):
    xp_collection.delete_many({"chat_id": chat_id})

def is_admin(member):
    return member and member.status in ("administrator", "creator")

def register(app):

    @app.on_message(filters.command(["bite", "spank", "tease"]) & filters.group)
    async def xp_command(client, message: Message):
        cmd = message.command[0].lstrip("/").lower()
        user = message.from_user
        gain = random.randint(1, 5)
        add_xp(message.chat.id, user.id, gain)
        await message.reply_text(f"{user.mention} got +{gain} XP for <b>{cmd}</b>!", parse_mode="html")

    @app.on_message(filters.command("naughtystats") & filters.group)
    async def naughtystats(client, message: Message):
        board = get_leaderboard(message.chat.id)
        if not board:
            return await message.reply_text("No XP recorded yet.")
        lines = ["📊 Naughty XP Stats:"]
        for i, doc in enumerate(board, start=1):
            uid = doc["user_id"]
            xp = doc["xp"]
            try:
                user: User = await client.get_users(uid)
                mention = user.mention
            except Exception as e:
                logger.warning(f"Could not fetch user {uid}: {e}")
                mention = f"<code>{uid}</code>"
            lines.append(f"{i}. {mention} — {xp} XP")
        await message.reply_text(
            "\n".join(lines),
            disable_web_page_preview=True,
            parse_mode="html"
        )

    @app.on_message(filters.command("resetxp") & filters.group)
    async def reset(client, message: Message):
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if message.from_user.id != OWNER_ID and not is_admin(member):
            return await message.reply_text("❌ Only admins can reset XP.")
        reset_xp(message.chat.id)
        await message.reply_text("✅ XP leaderboard has been reset.")
