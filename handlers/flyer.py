import os
import logging
from pymongo import MongoClient
from pyrogram import filters

# Set up logging
logger = logging.getLogger(__name__)

# Flyer images will be stored here
FLYER_DIR = "flyers"
os.makedirs(FLYER_DIR, exist_ok=True)

# MongoDB setup (use your own import/config)
mongo_client = MongoClient(os.environ["MONGO_URI"])
db = mongo_client.get_database(os.environ.get("MONGO_DB", "Succubot"))
flyers = db.flyers

def get_flyer_by_name(group_id, flyer_name):
    flyer = flyers.find_one({"group_id": group_id, "name": flyer_name})
    if flyer:
        return flyer["file_path"], flyer.get("caption", "")
    return None

def register(app):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message):
        user_id = message.from_user.id
        # Only allow admins or hardcoded owner to add flyers
        if not await is_admin_or_owner(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can add flyers.")
        if not (message.reply_to_message and message.reply_to_message.photo):
            return await message.reply("❌ Reply to an image with /addflyer <name> <caption>")

        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.reply("❌ Usage: /addflyer <name> <caption> (reply to image)")

        flyer_name = args[1]
        caption = args[2] if len(args) > 2 else ""
        flyer_file_path = os.path.join(FLYER_DIR, f"{message.chat.id}_{flyer_name}.jpg")
        await client.download_media(message.reply_to_message.photo.file_id, file_name=flyer_file_path)

        flyers.update_one(
            {"group_id": message.chat.id, "name": flyer_name},
            {"$set": {"file_path": flyer_file_path, "caption": caption}},
            upsert=True,
        )

        logger.info(f"Flyer '{flyer_name}' added/updated by {user_id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' saved. (with photo)")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin_or_owner(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can change flyers.")
        if not (message.reply_to_message and message.reply_to_message.photo):
            return await message.reply("❌ Reply to an image with /changeflyer <name>")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> (reply to new image)")
        flyer_name = args[1]
        flyer_file_path = os.path.join(FLYER_DIR, f"{message.chat.id}_{flyer_name}.jpg")
        await client.download_media(message.reply_to_message.photo.file_id, file_name=flyer_file_path)
        flyers.update_one(
            {"group_id": message.chat.id, "name": flyer_name},
            {"$set": {"file_path": flyer_file_path}},
            upsert=True,
        )
        logger.info(f"Flyer '{flyer_name}' image updated by {user_id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' image updated.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message):
        user_id = message.from_user.id
        if not await is_admin_or_owner(client, message.chat.id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        flyer_name = args[1]
        flyer = flyers.find_one_and_delete({"group_id": message.chat.id, "name": flyer_name})
        if flyer and "file_path" in flyer and os.path.isfile(flyer["file_path"]):
            os.remove(flyer["file_path"])
        logger.info(f"Flyer '{flyer_name}' deleted by {user_id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' deleted.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer_name = args[1]
        flyer = flyers.find_one({"group_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        try:
            await message.reply_photo(flyer["file_path"], caption=flyer.get("caption", ""))
        except Exception as e:
            logger.error(f"Failed to send flyer: {e}")
            await message.reply("❌ Failed to send flyer (file missing or invalid).")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message):
        flyer_list = flyers.find({"group_id": message.chat.id})
        names = [f"- {f['name']}" for f in flyer_list]
        await message.reply("Flyers:\n" + "\n".join(names) if names else "No flyers found.")

async def is_admin_or_owner(client, chat_id, user_id):
    if user_id == 6964994611:  # hardwired owner
        return True
    member = await client.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")
