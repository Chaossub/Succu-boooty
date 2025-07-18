import logging
from pyrogram import Client, filters
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DB_NAME", "succubot")
mongo_client = MongoClient(MONGO_URI)
flyers = mongo_client[MONGO_DBNAME]["flyers"]

OWNER_ID = 6964994611  # your user id

async def is_admin_or_owner(client, message):
    if message.from_user.id == OWNER_ID:
        return True
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("administrator", "creator")

def get_flyer_by_name(group_id, flyer_name):
    doc = flyers.find_one({"group_id": group_id, "name": flyer_name})
    if not doc:
        return None
    return doc.get("file_id"), doc.get("caption")

def register(app):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message):
        if not await is_admin_or_owner(client, message):
            return await message.reply("❌ Only admins can add flyers.")
        # Now, we just check if this message HAS a photo
        if not message.photo:
            return await message.reply("❌ Send a photo and use this command in the caption!\nUsage: /addflyer <name> <caption>")
        args = message.caption.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")
        flyer_name = args[1]
        caption = args[2] if len(args) > 2 else ""
        file_id = message.photo.file_id
        group_id = message.chat.id
        flyers.update_one(
            {"group_id": group_id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        logging.info(f"Flyer '{flyer_name}' added/updated by {message.from_user.id} in {group_id}")
        await message.reply(f"✅ Flyer '{flyer_name}' added/updated!")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message):
        if not await is_admin_or_owner(client, message):
            return await message.reply("❌ Only admins can change flyers.")
        if not message.photo:
            return await message.reply("❌ Send a photo and use this command in the caption!\nUsage: /changeflyer <name> <caption>")
        args = message.caption.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> <caption>")
        flyer_name = args[1]
        caption = args[2] if len(args) > 2 else ""
        file_id = message.photo.file_id
        group_id = message.chat.id
        flyers.update_one(
            {"group_id": group_id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{flyer_name}' updated!")

    # (deleteflyer, flyer, listflyers remain as in previous post)
