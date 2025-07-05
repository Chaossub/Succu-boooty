import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable not set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["SuccuBot"]
feds = db["federations"]

def register(app):

    @app.on_message(filters.command("createfed") & filters.group)
    async def create_fed(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /createfed <name>")
            return
        fed_name = args[1].strip()
        fed_id = f"fed-{message.chat.id}"
        existing = feds.find_one({"fed_id": fed_id})
        if existing:
            await message.reply("This group already has a federation.")
            return
        feds.insert_one({
            "fed_id": fed_id,
            "name": fed_name,
            "owner_id": message.from_user.id,
            "admins": [],
            "bans": []
        })
        await message.reply(f"✅ Federation <b>{fed_name}</b> created!\nFedID: <code>{fed_id}</code>")

    @app.on_message(filters.command("fedlist") & filters.group)
    async def fed_list(client, message: Message):
        fed_list = list(feds.find({}))
        if not fed_list:
            await message.reply("No federations found.")
            return
        text = "<b>Federations:</b>\n"
        for fed in fed_list:
            text += f"- <code>{fed['fed_id']}</code>: {fed.get('name', 'No name')}\n"
        await message.reply(text)
