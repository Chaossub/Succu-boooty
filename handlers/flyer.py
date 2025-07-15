import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# Mongo setup
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers

# Only allow certain user IDs to use admin commands
ADMIN_IDS = [6964994611]  # Replace/add admin IDs as needed

def admin_filter(_, __, m: Message):
    return m.from_user and m.from_user.id in ADMIN_IDS

def register(app):
    # Add flyer: With or without media, new message or as reply
    @app.on_message(filters.command("addflyer") & filters.create(admin_filter))
    async def addflyer(client, message: Message):
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply(
                "❌ Usage: /addflyer <name> <caption> (optionally attach an image, or reply to one)",
                quote=True,
            )
        flyer_name = args[1].strip()
        caption = args[2].strip()
        file_id = None

        # Check if media in same message
        if message.photo:
            file_id = message.photo.file_id
        elif message.document and message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        # Or if replying to a photo/document
        elif message.reply_to_message:
            if message.reply_to_message.photo:
                file_id = message.reply_to_message.photo.file_id
            elif (
                message.reply_to_message.document
                and message.reply_to_message.document.mime_type.startswith("image/")
            ):
                file_id = message.reply_to_message.document.file_id

        flyers.update_one(
            {"name": flyer_name},
            {"$set": {"name": flyer_name, "file_id": file_id, "caption": caption}},
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{flyer_name}' added{' with image.' if file_id else '.'}")

    # Get flyer
    @app.on_message(filters.command("flyer"))
    async def getflyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer = flyers.find_one({"name": args[1].strip()})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer.get("file_id"):
            await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

    # List flyers
    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message: Message):
        flyer_list = [f"• <b>{f['name']}</b>" for f in flyers.find({})]
        if flyer_list:
            await message.reply("📋 <b>Flyers:</b>\n" + "\n".join(flyer_list))
        else:
            await message.reply("No flyers added yet.")

    # Change flyer (replace media or text)
    @app.on_message(filters.command("changeflyer") & filters.create(admin_filter))
    async def changeflyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> (attach a new image or reply to a new image/message)")
        flyer_name = args[1].strip()
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        file_id = flyer.get("file_id")
        caption = flyer.get("caption", "")

        # New media/text in message?
        if message.photo:
            file_id = message.photo.file_id
        elif message.document and message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        elif message.text and message.text != args[0] + " " + flyer_name:
            caption = message.text.replace(args[0] + " " + flyer_name, "").strip()
        # Or in reply?
        elif message.reply_to_message:
            if message.reply_to_message.photo:
                file_id = message.reply_to_message.photo.file_id
            elif (
                message.reply_to_message.document
                and message.reply_to_message.document.mime_type.startswith("image/")
            ):
                file_id = message.reply_to_message.document.file_id
            elif message.reply_to_message.text:
                caption = message.reply_to_message.text

        flyers.update_one(
            {"name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption}},
        )
        await message.reply(f"✅ Flyer '{flyer_name}' updated.")

    # Delete flyer
    @app.on_message(filters.command("deleteflyer") & filters.create(admin_filter))
    async def deleteflyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        result = flyers.delete_one({"name": args[1].strip()})
        if result.deleted_count:
            await message.reply("✅ Flyer deleted.")
        else:
            await message.reply("❌ Flyer not found.")

