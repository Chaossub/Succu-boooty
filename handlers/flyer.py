import os
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message

# Mongo setup
MONGO_URI = os.environ.get("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["flyer_db"]
flyers = db.flyers

OWNER_ID = 6964994611
ADMINS = [OWNER_ID]

def is_admin(user_id):
    return user_id in ADMINS

def register(app):

    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can add flyers.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("Usage: `/addflyer <name> <caption>`\nOptionally attach a photo.", quote=True)
        flyer_name = args[1].strip().lower()
        caption = args[2].strip()
        photo_id = message.photo.file_id if message.photo else None
        flyer_data = {
            "chat_id": message.chat.id,
            "name": flyer_name,
            "caption": caption,
            "photo_id": photo_id,
        }
        flyers.update_one(
            {"chat_id": message.chat.id, "name": flyer_name},
            {"$set": flyer_data},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{flyer_name}' saved.{' (with photo)' if photo_id else ' (text only)'}")

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can change flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: `/changeflyer <name>` (reply to new photo/text)", quote=True)
        flyer_name = args[1].strip().lower()
        if message.reply_to_message:
            caption = message.reply_to_message.text or ""
            photo_id = message.reply_to_message.photo.file_id if message.reply_to_message.photo else None
        else:
            caption = ""
            photo_id = None
        if not (caption or photo_id):
            return await message.reply("❌ Reply to a new photo or text for the flyer content.")
        result = flyers.update_one(
            {"chat_id": message.chat.id, "name": flyer_name},
            {"$set": {"caption": caption, "photo_id": photo_id}},
        )
        if result.matched_count:
            await message.reply(f"✅ Flyer '{flyer_name}' updated.")
        else:
            await message.reply("❌ Flyer not found for update.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message: Message):
        if not is_admin(message.from_user.id):
            return await message.reply("❌ Only group admins/owner can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: `/deleteflyer <name>`", quote=True)
        flyer_name = args[1].strip().lower()
        result = flyers.delete_one({"chat_id": message.chat.id, "name": flyer_name})
        if result.deleted_count:
            await message.reply(f"✅ Flyer '{flyer_name}' deleted.")
        else:
            await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message: Message):
        found = flyers.find({"chat_id": message.chat.id})
        names = [doc["name"] for doc in found]
        if names:
            await message.reply("📄 Flyers in this group:\n" + "\n".join(f"- `{n}`" for n in names))
        else:
            await message.reply("No flyers found in this group.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: `/flyer <name>`", quote=True)
        flyer_name = args[1].strip().lower()
        flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer.get("photo_id"):
            await message.reply_photo(flyer["photo_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", "No caption."))

