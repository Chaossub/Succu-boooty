import os
import logging
from pyrogram import filters
from pymongo import MongoClient

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB", "succubot").lower()  # <--- always lowercase
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
flyers = db.flyers

ADMIN_IDS = {6964994611}  # <-- your Telegram ID, can add more

logger = logging.getLogger(__name__)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_flyer_by_name(group_id, flyer_name):
    flyer = flyers.find_one({"group_id": group_id, "name": flyer_name})
    if flyer:
        return flyer.get("file_id"), flyer.get("caption")
    return None

def register(app):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only admins can add flyers.")
            return

        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("❌ Reply to a photo to add a flyer.")
            return

        try:
            args = message.text.split(maxsplit=2)
            flyer_name = args[1]
            caption = args[2] if len(args) > 2 else ""
        except Exception:
            await message.reply("❌ Usage: /addflyer <name> <caption> (reply to photo)")
            return

        file_id = message.reply_to_message.photo.file_id
        flyers.update_one(
            {"group_id": message.chat.id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
            upsert=True
        )
        logger.info(f"Flyer '{flyer_name}' added/updated by {message.from_user.id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' saved/updated.")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only admins can change flyers.")
            return

        if not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("❌ Reply to a new photo to update the flyer.")
            return

        try:
            flyer_name = message.text.split(maxsplit=1)[1]
        except Exception:
            await message.reply("❌ Usage: /changeflyer <name> (reply to new photo)")
            return

        file_id = message.reply_to_message.photo.file_id
        flyers.update_one(
            {"group_id": message.chat.id, "name": flyer_name},
            {"$set": {"file_id": file_id}},
            upsert=True
        )
        logger.info(f"Flyer '{flyer_name}' updated by {message.from_user.id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' image updated.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message):
        try:
            flyer_name = message.text.split(maxsplit=1)[1]
        except Exception:
            await message.reply("❌ Usage: /flyer <name>")
            return

        flyer = flyers.find_one({"group_id": message.chat.id, "name": flyer_name})
        if flyer:
            await message.reply_photo(
                photo=flyer["file_id"],
                caption=flyer.get("caption", "")
            )
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only admins can delete flyers.")
            return

        try:
            flyer_name = message.text.split(maxsplit=1)[1]
        except Exception:
            await message.reply("❌ Usage: /deleteflyer <name>")
            return

        result = flyers.delete_one({"group_id": message.chat.id, "name": flyer_name})
        if result.deleted_count:
            logger.info(f"Flyer '{flyer_name}' deleted by {message.from_user.id} in {message.chat.id}")
            await message.reply(f"✅ Flyer '{flyer_name}' deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message):
        flyer_list = list(flyers.find({"group_id": message.chat.id}))
        if not flyer_list:
            await message.reply("No flyers found in this group.")
        else:
            names = [f"• {f['name']}" for f in flyer_list]
            await message.reply("Flyers in this group:\n" + "\n".join(names))

