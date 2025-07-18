import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pymongo import MongoClient
from pyrogram.types import Message

# Set up logging
logger = logging.getLogger(__name__)

# MongoDB setup (reads env vars)
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGO_DB_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME", "succubot")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
flyers = db.flyers

OWNER_ID = 6964994611  # Your Telegram ID

def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except Exception as e:
        logger.warning(f"Admin check failed: {e}")
        return False

def get_flyer_by_name(group_id, name):
    doc = flyers.find_one({"name": name})
    if doc:
        return doc.get("file_id"), doc.get("caption")
    return None

def list_flyers():
    return [doc['name'] for doc in flyers.find()]

def register(app: Client):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        # Restrict to admin/owner only
        if not is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can add flyers.")
        if not message.photo and len(message.command) < 3:
            return await message.reply("❌ Usage: Send a photo with caption: /addflyer <name> <caption>, or /addflyer <name> <caption> for text flyers.")
        # Photo flyer
        if message.photo:
            args = message.caption.split(maxsplit=2) if message.caption else []
            if len(args) < 2:
                return await message.reply("❌ Usage: Send photo with caption: /addflyer <name> <caption>")
            flyer_name = args[1]
            caption = args[2] if len(args) > 2 else ""
            file_id = message.photo.file_id
        # Text flyer
        else:
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                return await message.reply("❌ Usage: /addflyer <name> <caption>")
            flyer_name = args[1]
            caption = args[2]
            file_id = None
        flyers.update_one(
            {"name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True,
        )
        logger.info(f"Flyer '{flyer_name}' added/updated by {user_id}")
        await message.reply(f"✅ Flyer '{flyer_name}' saved globally.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can change flyers.")
        if not message.photo and len(message.command) < 3:
            return await message.reply("❌ Usage: Send a new photo with caption: /changeflyer <name> <caption> (or just /changeflyer <name> <caption> for text)")
        # Photo flyer
        if message.photo:
            args = message.caption.split(maxsplit=2) if message.caption else []
            if len(args) < 2:
                return await message.reply("❌ Usage: Send photo with caption: /changeflyer <name> <caption>")
            flyer_name = args[1]
            caption = args[2] if len(args) > 2 else ""
            file_id = message.photo.file_id
        # Text flyer
        else:
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                return await message.reply("❌ Usage: /changeflyer <name> <caption>")
            flyer_name = args[1]
            caption = args[2]
            file_id = None
        flyers.update_one(
            {"name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True,
        )
        logger.info(f"Flyer '{flyer_name}' changed by {user_id}")
        await message.reply(f"✅ Flyer '{flyer_name}' updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split()
        if len(args) != 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        flyer_name = args[1]
        flyers.delete_one({"name": flyer_name})
        logger.info(f"Flyer '{flyer_name}' deleted by {user_id}")
        await message.reply(f"🗑️ Flyer '{flyer_name}' deleted.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message: Message):
        all_flyers = list_flyers()
        if not all_flyers:
            return await message.reply("No flyers found.")
        await message.reply("Flyers:\n" + "\n".join(f"- {f}" for f in all_flyers))

    @app.on_message(filters.command("flyer") & filters.group)
    async def getflyer_handler(client, message: Message):
        args = message.text.split()
        if len(args) != 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer_name = args[1]
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply(f"❌ Flyer '{flyer_name}' not found.")
        if flyer.get("file_id"):
            await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

# This export is needed for the scheduler and other modules:
__all__ = ["register", "get_flyer_by_name"]

