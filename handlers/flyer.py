import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["succubot"]
flyers = db.flyers

def register(app):
    @app.on_message(filters.command("addflyer"))
    async def addFlyer(client, message: Message):
        if not message.text:
            return await message.reply("❌ Usage: <code>/addflyer &lt;name&gt; &lt;caption&gt;</code> with an attached photo.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: <code>/addflyer &lt;name&gt; &lt;caption&gt;</code> (with a photo attached).")
        flyer_name = args[1].lower()
        caption = args[2]

        if not message.photo:
            return await message.reply("❌ Please attach a photo for the flyer.")

        file_id = message.photo.file_id

        flyers.update_one(
            {"name": flyer_name, "chat_id": message.chat.id},
            {"$set": {
                "name": flyer_name,
                "caption": caption,
                "file_id": file_id,
                "chat_id": message.chat.id,
            }},
            upsert=True,
        )

        await message.reply(f"✅ Flyer '<b>{flyer_name}</b>' added.")

    @app.on_message(filters.command("flyer"))
    async def getFlyer(client, message: Message):
        if not message.text:
            return await message.reply("❌ Usage: <code>/flyer &lt;name&gt;</code>")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: <code>/flyer &lt;name&gt;</code>")
        flyer_name = args[1].lower()

        flyer = flyers.find_one({"name": flyer_name, "chat_id": message.chat.id})
        if not flyer:
            return await message.reply(f"❌ No flyer named '{flyer_name}' found.")

        await message.reply_photo(flyer['file_id'], caption=flyer['caption'])

    @app.on_message(filters.command("listflyers"))
    async def listFlyers(client, message: Message):
        cursor = flyers.find({"chat_id": message.chat.id})
        flyer_list = [doc["name"] for doc in cursor]
        if not flyer_list:
            return await message.reply("No flyers found.")
        await message.reply("📋 Flyers: " + ", ".join(f"<b>{name}</b>" for name in flyer_list))

    @app.on_message(filters.command("deleteflyer"))
    async def deleteFlyer(client, message: Message):
        if not message.text:
            return await message.reply("❌ Usage: <code>/deleteflyer &lt;name&gt;</code>")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: <code>/deleteflyer &lt;name&gt;</code>")
        flyer_name = args[1].lower()
        result = flyers.delete_one({"name": flyer_name, "chat_id": message.chat.id})
        if result.deleted_count == 0:
            return await message.reply(f"❌ No flyer named '{flyer_name}' found.")
        await message.reply(f"✅ Flyer '<b>{flyer_name}</b>' deleted.")

    @app.on_message(filters.command("changeflyer"))
    async def changeFlyer(client, message: Message):
        if not message.reply_to_message or not message.reply_to_message.photo:
            return await message.reply("❌ Reply to a new photo with <code>/changeflyer &lt;name&gt;</code>")
        if not message.text:
            return await message.reply("❌ Usage: <code>/changeflyer &lt;name&gt;</code>")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: <code>/changeflyer &lt;name&gt;</code>")
        flyer_name = args[1].lower()
        new_file_id = message.reply_to_message.photo.file_id

        flyer = flyers.find_one({"name": flyer_name, "chat_id": message.chat.id})
        if not flyer:
            return await message.reply(f"❌ No flyer named '{flyer_name}' found.")

        flyers.update_one(
            {"name": flyer_name, "chat_id": message.chat.id},
            {"$set": {"file_id": new_file_id}}
        )

        await message.reply(f"✅ Flyer '<b>{flyer_name}</b>' photo updated.")

# End of flyer.py

