from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyer_collection = db["flyers"]

OWNER_ID = 6964994611

def is_admin(user_id):
    return user_id == OWNER_ID

@Client.on_message(filters.command("addflyer"))
async def addflyer_handler(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("Only admins can add flyers.")
        return
    args = (message.text or message.caption or "").split(maxsplit=2)
    if len(args) < 2:
        await message.reply("Usage: /addflyer <name> <caption> (attach photo for image flyer)")
        return
    name = args[1].strip().lower()
    caption = args[2] if len(args) > 2 else ""
    file_id = message.photo.file_id if message.photo else None
    flyer_type = "photo" if file_id else "text"
    flyer_collection.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "caption": caption,
            "file_id": file_id,
            "type": flyer_type
        }},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' saved{' with photo' if file_id else ''}.")

@Client.on_message(filters.command("flyer"))
async def flyer_handler(client, message: Message):
    args = (message.text or message.caption or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /flyer <name>")
        return
    name = args[1].strip().lower()
    flyer = flyer_collection.find_one({"name": name})
    if not flyer:
        await message.reply(f"No flyer found with name '{name}'.")
        return
    if flyer.get("file_id") and flyer.get("type") == "photo":
        await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

