import os
import random
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message

# 1) Load your Mongo URI
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise RuntimeError("Please set MONGO_URI or MONGODB_URI in your environment")

# 2) Choose a database name (does not need to appear in the URI)
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
    return member.status in ("administrator", "creator")

def register(app):

    @app.on_message(filters.command(["bite", "spank", "tease"]) & filters.group)
    async def xp_command(client, message: Message):
        cmd = message.text.split()[0][1:].lower()
        user = message.from_user
        gain = random.randint(1, 5)
        add_xp(message.chat.id, user.id, gain)
        await message.reply_text(f"{user.mention} got +{gain} XP for **{cmd}**!")

    @app.on_message(filters.command("leaderboard") & filters.group)
    async def leaderboard(client, message: Message):
        board = get_leaderboard(message.chat.id)
        if not board:
            return await message.reply_text("No XP recorded yet.")
        lines = ["🏆 Top XP Leaderboard:"]
        for i, doc in enumerate(board, start=1):
            uid = doc["user_id"]
            xp = doc["xp"]
            lines.append(f"{i}. <a href='tg://user?id={uid}'>User</a> — {xp} XP")
        await message.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.command("resetxp") & filters.group)
    async def reset(client, message: Message):
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if message.from_user.id != OWNER_ID and not is_admin(member):
            return await message.reply_text("❌ Only admins can reset XP.")
        reset_xp(message.chat.id)
        await message.reply_text("✅ XP leaderboard has been reset.")
