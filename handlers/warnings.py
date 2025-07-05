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
    if user_id == OWNER_ID:
        return True
    return chat_member and chat_member.status in ("administrator", "creator")

def register(app):

    async def get_target_user(message: Message):
        if not message.reply_to_message:
            await message.reply("You must reply to the user for this command.")
            logging.info("Command failed: no reply_to_message")
            return None
        user = message.reply_to_message.from_user
        if not user or not user.id:
            await message.reply("Could not find the user to target.")
            logging.info("Command failed: reply_to_message has no valid user")
            return None
        return user

    @app.on_message(filters.command("warn") & filters.group)
    async def warn_user(client, message: Message):
        logging.info(f"Received /warn from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can issue warnings.")
            return

        user = await get_target_user(message)
        if not user:
            return

        warnings_collection.update_one(
            {"user_id": user.id},
            {"$inc": {"count": 1}},
            upsert=True
        )
        doc = warnings_collection.find_one({"user_id": user.id})
        count = doc.get("count", 1)
        await message.reply(f"{user.mention} has been warned. Total warnings: {count}")

    @app.on_message(filters.command("warns") & filters.group)
    async def check_warns(client, message: Message):
        user = None
        if message.reply_to_message:
            user = message.reply_to_message.from_user
        else:
            user = message.from_user

        doc = warnings_collection.find_one({"user_id": user.id})
        count = doc.get("count", 0) if doc else 0
        await message.reply(f"{user.mention} has {count} warning(s).")

    @app.on_message(filters.command("resetwarns") & filters.group)
    async def reset_warns(client, message: Message):
        logging.info(f"Received /resetwarns from {message.from_user.id} in {message.chat.id}")
        chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if not is_admin(chat_member, message.from_user.id):
            await message.reply("Only admins can reset warnings.")
            return

        user = await get_target_user(message)
        if not user:
            return

        warnings_collection.delete_one({"user_id": user.id})
        await message.reply(f"{user.mention}'s warnings have been reset.")
