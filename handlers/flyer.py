from pyrogram import filters
from pyrogram.types import Message
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

# --- Flyer Commands ---

async def addflyer_handler(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("Only admins can add flyers.")
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3 and not message.photo:
        await message.reply("Usage: /addflyer <name> <caption> (attach photo for image flyer)")
        return
    name = args[1].strip().lower()
    caption = args[2] if len(args) > 2 else ""
    photo_id = message.photo.file_id if message.photo else None
    flyer_type = "photo" if photo_id else "text"
    flyer_collection.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "caption": caption,
            "photo_id": photo_id,
            "type": flyer_type
        }},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' saved{' with photo' if photo_id else ''}.")

async def flyer_handler(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /flyer <name>")
        return
    name = args[1].strip().lower()
    flyer = flyer_collection.find_one({"name": name})
    if not flyer:
        await message.reply(f"No flyer found with name '{name}'.")
        return
    if flyer.get("photo_id") and flyer.get("type") == "photo":
        await message.reply_photo(flyer["photo_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

async def listflyers_handler(client, message: Message):
    flyers = list(flyer_collection.find({}, {"name": 1}))
    if not flyers:
        await message.reply("No flyers found.")
        return
    msg = "Available flyers:\n" + "\n".join(f"- {f['name']}" for f in flyers)
    await message.reply(msg)

async def deleteflyer_handler(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("Only admins can delete flyers.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /deleteflyer <name>")
        return
    name = args[1].strip().lower()
    flyer_collection.delete_one({"name": name})
    await message.reply(f"🗑️ Flyer '{name}' deleted.")

# -- REGISTER ALL FLYER COMMANDS (IN GROUPS) --
def register(app):
    app.add_handler(filters.command("addflyer") & filters.group, addflyer_handler)
    app.add_handler(filters.command("flyer") & filters.group, flyer_handler)
    app.add_handler(filters.command("listflyers") & filters.group, listflyers_handler)
    app.add_handler(filters.command("deleteflyer") & filters.group, deleteflyer_handler)
    # Add more flyer-related handlers as needed

