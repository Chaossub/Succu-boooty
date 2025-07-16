import os
import logging
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message

logging.basicConfig(level=logging.INFO)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable not set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]
warnings_collection = db["warnings"]

OWNER_ID = 6964994611

def is_admin(chat_member, user_id):
    return user_id == OWNER_ID or (chat_member and chat_member.status in ("administrator", "creator"))

async def get_target_user(client, message: Message):
    # Prefer reply, fallback to /warn @username or /warn user_id
    if message.reply_to_message:
        return message.reply_to_message.from_user
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2:
        ref = parts[1].strip()
        try:
            if ref.startswith("@"):
                return await client.get_users(ref)
            elif ref.isdigit():
                return await client.get_users(int(ref))
        except Exception as e:
            await message.reply(f"Could not find user: <code>{e}</code>")
            return None
    await message.reply("Reply to a user or use /warn @username or user_id")
    return None

def register(app):

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        logging.info(f"Received /warn from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can issue warnings.")
            return
        user = await get_target_user(client, message)
        if not user:
            return
        warnings_collection.update_one(
            {"chat_id": message.chat.id, "user_id": user.id},
            {"$inc": {"count": 1}},
            upsert=True
        )
        doc = warnings_collection.find_one({"chat_id": message.chat.id, "user_id": user.id})
        count = doc.get("count", 1)
        await message.reply(f"{user.mention} has been warned. Total warnings: {count}")

    @app.on_message(filters.command("warns") & filters.group)
    async def check_warns(client, message: Message):
        user = None
        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            user = message.from_user
        doc = warnings_collection.find_one({"chat_id": message.chat.id, "user_id": user.id})
        count = doc.get("count", 0) if doc else 0
        await message.reply(f"{user.mention} has {count} warning(s).")

    @app.on_message(filters.command("resetwarns") & filters.group)
    async def reset_warns(client, message: Message):
        logging.info(f"Received /resetwarns from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can reset warnings.")
            return
        user = await get_target_user(client, message)
        if not user:
            return
        warnings_collection.delete_one({"chat_id": message.chat.id, "user_id": user.id})
        await message.reply(f"{user.mention}'s warnings have been reset.")

