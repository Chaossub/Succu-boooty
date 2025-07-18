from pyrogram import filters
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyer_collection = db["flyers"]

OWNER_ID = 6964994611

def is_admin(user_id):
    return user_id == OWNER_ID

def register(app):
    @app.on_message(filters.command("addflyer"))
    async def addflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can add flyers.")
            return

        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=2)
        if len(args) < 2:
            await message.reply("Usage: /addflyer <name> <caption> (attach or reply to photo for image flyer)")
            return

        name = args[1].strip().lower()
        caption = args[2] if len(args) > 2 else ""
        file_id = None
        if message.photo:
            file_id = message.photo.file_id
        elif message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id

        flyer_type = "photo" if file_id else "text"

        flyer_collection.update_one(
            {"name": name},
            {"$set": {
                "name": name,
                "caption": caption,
                "file_id": file_id,
                "type": flyer_type
            }},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{name}' saved{' with photo' if file_id else ''}.")

    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message):
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /flyer <name>")
            return
        name = args[1].strip().lower()
        flyer = flyer_collection.find_one({"name": name})
        if not flyer:
            await message.reply(f"No flyer found with name '{name}'.")
            return
        if flyer.get("file_id") and flyer.get("type") == "photo":
            await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

    @app.on_message(filters.command("listflyers"))
    async def listflyers_handler(client, message):
        flyers = list(flyer_collection.find({}, {"name": 1}))
        if not flyers:
            await message.reply("No flyers found.")
            return
        msg = "Available flyers:\n" + "\n".join(f"- {f['name']}" for f in flyers)
        await message.reply(msg)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can delete flyers.")
            return
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /deleteflyer <name>")
            return
        name = args[1].strip().lower()
        flyer_collection.delete_one({"name": name})
        await message.reply(f"🗑️ Flyer '{name}' deleted.")

    @app.on_message(filters.command("textflyer"))
    async def textflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can convert flyers to text-only.")
            return
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /textflyer <name>")
            return
        name = args[1].strip().lower()
        flyer = flyer_collection.find_one({"name": name})
        if not flyer:
            await message.reply(f"No flyer found with name '{name}'.")
            return
        flyer_collection.update_one(
            {"name": name},
            {"$set": {"file_id": None, "type": "text"}}
        )
        await message.reply(f"✅ Flyer '{name}' is now text-only. Use /flyer {name} to check.")
