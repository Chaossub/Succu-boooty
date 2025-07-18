import logging
from pyrogram import Client, filters
from pymongo import MongoClient
import os

# --- MongoDB setup ---
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DB_NAME", "succubot")
mongo_client = MongoClient(MONGO_URI)
flyers = mongo_client[MONGO_DBNAME]["flyers"]

OWNER_ID = 6964994611  # YOUR user id

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
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Reply to a photo to add as a flyer.\nUsage: /addflyer <name> <caption>")
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption>")
        flyer_name = args[1]
        caption = args[2] if len(args) > 2 else ""
        file_id = message.reply_to_message.photo.file_id
        group_id = message.chat.id
        flyers.update_one(
            {"group_id": group_id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        logging.info(f"Flyer '{flyer_name}' added/updated by {message.from_user.id} in {group_id}")
        await message.reply(f"✅ Flyer '{flyer_name}' added/updated!")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message):
        if not await is_admin_or_owner(client, message):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split()
        if len(args) != 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        flyer_name = args[1]
        group_id = message.chat.id
        res = flyers.delete_one({"group_id": group_id, "name": flyer_name})
        if res.deleted_count:
            await message.reply(f"✅ Flyer '{flyer_name}' deleted.")
        else:
            await message.reply(f"❌ Flyer '{flyer_name}' not found.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message):
        if not await is_admin_or_owner(client, message):
            return await message.reply("❌ Only admins can change flyers.")
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Reply to a photo to update flyer.\nUsage: /changeflyer <name> <caption>")
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> <caption>")
        flyer_name = args[1]
        caption = args[2] if len(args) > 2 else ""
        file_id = message.reply_to_message.photo.file_id
        group_id = message.chat.id
        flyers.update_one(
            {"group_id": group_id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{flyer_name}' updated!")

    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message):
        args = message.text.split()
        if len(args) != 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer_name = args[1]
        group_id = message.chat.id
        flyer = get_flyer_by_name(group_id, flyer_name)
        if not flyer:
            return await message.reply(f"❌ Flyer '{flyer_name}' not found.")
        file_id, caption = flyer
        await message.reply_photo(file_id, caption=caption or "")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message):
        group_id = message.chat.id
        docs = list(flyers.find({"group_id": group_id}))
        if not docs:
            return await message.reply("No flyers found.")
        flyer_names = [doc["name"] for doc in docs]
        await message.reply("📜 Flyers in this group:\n" + "\n".join(flyer_names))
