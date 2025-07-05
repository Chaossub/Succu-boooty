import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable not set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["SuccuBot"]
feds = db["federations"]
groups = db["groups"]

SUPER_ADMIN_ID = 6964994611

def is_fed_admin(user_id, fed_id):
    fed = feds.find_one({"fed_id": fed_id})
    if not fed:
        return False
    if user_id == fed["owner_id"]:
        return True
    if user_id in fed.get("admins", []):
        return True
    if user_id == SUPER_ADMIN_ID:
        return True
    return False

def register(app):

    @app.on_message(filters.command("createfed") & filters.group)
    async def create_fed(client, message: Message):
        logging.info(f"Received /createfed command from user {message.from_user.id} in chat {message.chat.id}")

        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await message.reply("Usage: /createfed <name>")
            return

        fed_name = args[1].strip()
        fed_id = f"fed-{message.chat.id}"

        existing = feds.find_one({"fed_id": fed_id})
        if existing:
            await message.reply("This group already has a federation.")
            return

        try:
            feds.insert_one({
                "fed_id": fed_id,
                "name": fed_name,
                "owner_id": message.from_user.id,
                "admins": [],
                "bans": []
            })
        except Exception as e:
            await message.reply(f"Database error:\n<code>{e}</code>")
            logging.error(f"Failed to insert federation: {e}")
            return

        await message.reply(f"✅ Federation <b>{fed_name}</b> created!\nFedID: <code>{fed_id}</code>")

    @app.on_message(filters.command("fedlist") & filters.group)
    async def fed_list(client, message: Message):
        logging.info(f"Received /fedlist command from user {message.from_user.id} in chat {message.chat.id}")
        fed_list = list(feds.find({}))
        if not fed_list:
            await message.reply("No federations found.")
            return
        text = "<b>Federations:</b>\n"
        for fed in fed_list:
            text += f"- <code>{fed['fed_id']}</code>: {fed.get('name', 'No name')}\n"
        await message.reply(text)

    # Add other federation commands here as needed...
