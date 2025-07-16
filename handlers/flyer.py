import os
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from pyrogram.enums import ChatMemberStatus
from pymongo import MongoClient

# Setup your DB connection
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo.flyers

OWNER_ID = int(os.environ.get("OWNER_ID", "6964994611"))  # Set your Telegram ID

async def is_admin(client, message: Message) -> bool:
    if message.from_user and message.from_user.id == OWNER_ID:
        return True
    chat_member = await client.get_chat_member(message.chat.id, message.from_user.id)
    return chat_member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)

# Add flyer (photo+caption or text only)
async def addflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        await message.reply("❌ You must be an admin to use this command.")
        return

    # If photo is attached
    if message.photo:
        args = message.caption.split(maxsplit=2) if message.caption else []
    else:
        args = message.text.split(maxsplit=2) if message.text else []

    if len(args) < 3 or not args[1].strip():
        return await message.reply("❌ Usage: /addflyer <name> <caption> (with an attached photo, or text only)")

    flyer_name, flyer_caption = args[1], args[2]

    flyer_data = {
        "chat_id": message.chat.id,
        "name": flyer_name.lower(),
        "caption": flyer_caption,
        "file_id": message.photo.file_id if message.photo else None,
        "type": "photo" if message.photo else "text",
    }
    flyers_col.update_one(
        {"chat_id": message.chat.id, "name": flyer_name.lower()},
        {"$set": flyer_data},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> saved!")

# Get flyer by name
async def getflyer_handler(client, message: Message):
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
        return await message.reply("❌ Usage: /flyer <name>")

    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": args[1].lower()})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    if flyer.get("type") == "photo" and flyer.get("file_id"):
        await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

# Delete flyer by name
async def deleteflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")

    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")

    result = flyers_col.delete_one({"chat_id": message.chat.id, "name": args[1].lower()})
    if result.deleted_count:
        await message.reply(f"🗑️ Flyer <b>{args[1]}</b> deleted.")
    else:
        await message.reply("❌ Flyer not found.")

# List flyers in the group
async def listflyers_handler(client, message: Message):
    flyers = list(flyers_col.find({"chat_id": message.chat.id}))
    if not flyers:
        await message.reply("No flyers found in this group.")
        return
    flyer_names = [f"<b>{f['name']}</b>" for f in flyers]
    await message.reply("📋 Flyers in this group:\n" + "\n".join(flyer_names))

# Change flyer (when replying to an image or text)
async def changeflyer_handler(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply("❌ You must be an admin to use this command.")
    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) < 2:
        return await message.reply("❌ Usage: /changeflyer <name> (attach new photo/text or reply to an image/text)")

    flyer_name = args[1].lower()
    # If replying to photo/text, update it
    if message.reply_to_message:
        reply = message.reply_to_message
        flyer_data = {
            "chat_id": message.chat.id,
            "name": flyer_name,
            "caption": reply.caption or reply.text or "",
            "file_id": reply.photo.file_id if reply.photo else None,
            "type": "photo" if reply.photo else "text",
        }
    elif message.photo:
        flyer_data = {
            "chat_id": message.chat.id,
            "name": flyer_name,
            "caption": message.caption or "",
            "file_id": message.photo.file_id,
            "type": "photo",
        }
    else:
        flyer_data = {
            "chat_id": message.chat.id,
            "name": flyer_name,
            "caption": " ".join(args[2:]) if len(args) > 2 else "",
            "file_id": None,
            "type": "text",
        }
    flyers_col.update_one(
        {"chat_id": message.chat.id, "name": flyer_name},
        {"$set": flyer_data},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> updated!")

from pyrogram.handlers import MessageHandler

def register(app):
    app.add_handler(MessageHandler(addflyer_handler, filters.command("addflyer")))
    app.add_handler(MessageHandler(getflyer_handler, filters.command("flyer")))
    app.add_handler(MessageHandler(deleteflyer_handler, filters.command("deleteflyer")))
    app.add_handler(MessageHandler(listflyers_handler, filters.command("listflyers")))
    app.add_handler(MessageHandler(changeflyer_handler, filters.command("changeflyer")))
