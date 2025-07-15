import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME", "SuccuBot")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
flyers = db.flyers

def register(app):
    # Add flyer (with photo or just caption/text)
    @app.on_message(filters.command("addflyer") & (filters.photo | filters.text))
    async def addflyer(client, message: Message):
        # Prefer caption (photo), fallback to text
        input_text = message.caption or message.text
        if not input_text:
            return await message.reply(
                "❌ Usage: Send /addflyer <name> <caption> as caption (photo) or text command."
            )

        args = input_text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply(
                "❌ Usage: /addflyer <name> <caption> (attach photo for image flyer)"
            )

        _, name, caption = args
        file_id = message.photo.file_id if message.photo else None

        flyers.update_one(
            {"chat_id": message.chat.id, "name": name},
            {
                "$set": {
                    "chat_id": message.chat.id,
                    "name": name,
                    "caption": caption,
                    "file_id": file_id,
                    "updated_at": message.date,
                }
            },
            upsert=True,
        )
        await message.reply(f"✅ Flyer '{name}' added.")

    # Get flyer by name
    @app.on_message(filters.command("flyer"))
    async def flyer_cmd(client, message: Message):
        args = (message.text or message.caption or "").split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = args[1]
        flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
        if not flyer:
            return await message.reply(f"❌ Flyer '{name}' not found.")
        if flyer.get("file_id"):
            await message.reply_photo(
                flyer["file_id"], caption=flyer.get("caption", "")
            )
        else:
            await message.reply(flyer.get("caption", "No caption."))

    # Delete flyer
    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer(client, message: Message):
        args = (message.text or message.caption or "").split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1]
        result = flyers.delete_one({"chat_id": message.chat.id, "name": name})
        if result.deleted_count:
            await message.reply(f"✅ Flyer '{name}' deleted.")
        else:
            await message.reply(f"❌ Flyer '{name}' not found.")

    # List all flyers
    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message: Message):
        docs = flyers.find({"chat_id": message.chat.id})
        names = [doc["name"] for doc in docs]
        if not names:
            return await message.reply("No flyers found in this group.")
        await message.reply("📋 Flyers in this group:\n" + "\n".join(f"- {n}" for n in names))
