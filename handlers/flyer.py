# handlers/flyer.py

import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

# ------- CONFIGURE THIS: Import or define your MongoClient and DB ---------
# Replace the next two lines with your own setup if you already import globally!
mongo_client = MongoClient("YOUR_MONGODB_URI")  # <-- SET THIS!
mongo_db = mongo_client["YOUR_DB_NAME"]         # <-- SET THIS!

# -------------------- MONGO HELPERS ---------------------
def save_flyer(group_id, flyer_name, file_id, caption):
    flyers = mongo_db.flyers
    flyers.update_one(
        {"group_id": group_id, "name": flyer_name},
        {"$set": {"file_id": file_id, "caption": caption}},
        upsert=True,
    )

def get_flyer_by_name(group_id, flyer_name):
    flyers = mongo_db.flyers
    flyer = flyers.find_one({"group_id": group_id, "name": flyer_name})
    if flyer:
        return flyer["file_id"], flyer["caption"]
    return None, None

def list_flyer_names(group_id):
    flyers = mongo_db.flyers
    return [f["name"] for f in flyers.find({"group_id": group_id})]

def delete_flyer(group_id, flyer_name):
    flyers = mongo_db.flyers
    flyers.delete_one({"group_id": group_id, "name": flyer_name})

# -------------------- /addflyer HANDLER ---------------------
async def addflyer_handler(client, message: Message):
    # Accepts: /addflyer <name> <caption> + photo (attached or in reply)
    cmd = message.text or message.caption
    if not cmd:
        await message.reply("❌ Usage: /addflyer <name> <caption> (attach photo or reply to a photo)")
        return

    parts = cmd.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("❌ Usage: /addflyer <name> <caption> (attach photo or reply to a photo)")
        return

    _, flyer_name, flyer_caption = parts

    # Look for photo in message or reply
    file_id = None
    if message.photo:
        file_id = message.photo.file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        file_id = message.reply_to_message.photo.file_id

    if not file_id:
        await message.reply("❌ You must attach a photo or reply to a photo message.")
        return

    try:
        save_flyer(message.chat.id, flyer_name, file_id, flyer_caption)
        await message.reply(f"✅ Flyer '{flyer_name}' saved. (with photo)")
    except Exception as e:
        logging.exception("Failed to save flyer")
        await message.reply(f"❌ Failed to save flyer: {e}")

# -------------------- /flyer HANDLER (show a flyer) ---------------------
async def flyer_handler(client, message: Message):
    cmd = message.text or message.caption
    if not cmd or len(cmd.split(maxsplit=1)) < 2:
        await message.reply("❌ Usage: /flyer <name>")
        return
    _, flyer_name = cmd.split(maxsplit=1)
    file_id, caption = get_flyer_by_name(message.chat.id, flyer_name)
    if not file_id:
        await message.reply("❌ No flyer found with that name.")
        return
    try:
        await message.reply_photo(file_id, caption=caption or "")
    except Exception as e:
        logging.exception("Failed to send flyer")
        await message.reply(f"❌ Failed to send flyer: {e}")

# -------------------- /listflyers HANDLER ---------------------
async def listflyers_handler(client, message: Message):
    flyers = list_flyer_names(message.chat.id)
    if not flyers:
        await message.reply("No flyers saved yet.")
        return
    msg = "Flyers in this group:\n" + "\n".join(f"- {f}" for f in flyers)
    await message.reply(msg)

# -------------------- /deleteflyer HANDLER ---------------------
async def deleteflyer_handler(client, message: Message):
    cmd = message.text or message.caption
    if not cmd or len(cmd.split(maxsplit=1)) < 2:
        await message.reply("❌ Usage: /deleteflyer <name>")
        return
    _, flyer_name = cmd.split(maxsplit=1)
    delete_flyer(message.chat.id, flyer_name)
    await message.reply(f"✅ Flyer '{flyer_name}' deleted (if it existed).")

# -------------------- REGISTER HANDLERS ---------------------
def register(app):
    app.add_handler(filters.command("addflyer") & filters.group, addflyer_handler)
    app.add_handler(filters.command("flyer") & filters.group, flyer_handler)
    app.add_handler(filters.command("listflyers") & filters.group, listflyers_handler)
    app.add_handler(filters.command("deleteflyer") & filters.group, deleteflyer_handler)
