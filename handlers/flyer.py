import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

OWNER_ID = 6964994611  # Your Telegram user ID (always admin)

async def is_admin(client, chat_id, user_id):
    if user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers = mongo.flyers

# Add a flyer (photo or text, admin-only)
async def addflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can add flyers.")
    if len(message.command) < 3:
        return await message.reply("Usage: <code>/addflyer name caption</code> (attach photo for image flyer, or just text)")
    flyer_name = message.command[1].lower()
    caption = message.text.split(None, 2)[2]
    flyer_data = {
        "chat_id": message.chat.id,
        "name": flyer_name,
        "caption": caption,
    }
    if message.photo:
        flyer_data["file_id"] = message.photo.file_id
    flyers.update_one(
        {"chat_id": message.chat.id, "name": flyer_name},
        {"$set": flyer_data},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{flyer_name}</b> saved!")

# Get a flyer
async def flyer_handler(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/flyer name</code>")
    flyer_name = message.command[1].lower()
    flyer = flyers.find_one({"chat_id": message.chat.id, "name": flyer_name})
    if not flyer:
        return await message.reply("❌ No flyer found by that name.")
    if "file_id" in flyer:
        await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

# List all flyers
async def listflyers_handler(client, message: Message):
    flyer_list = flyers.find({"chat_id": message.chat.id})
    names = [f"<code>{f['name']}</code>" for f in flyer_list]
    if not names:
        return await message.reply("No flyers saved in this group.")
    await message.reply("Flyers:\n" + "\n".join(names))

# Delete a flyer (admin-only)
async def deleteflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Only admins can delete flyers.")
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/deleteflyer name</code>")
    flyer_name = message.command[1].lower()
    res = flyers.delete_one({"chat_id": message.chat.id, "name": flyer_name})
    if res.deleted_count:
        await message.reply(f"🗑️ Deleted flyer <b>{flyer_name}</b>.")
    else:
        await message.reply("❌ No flyer found by that name.")

# Register all flyer commands
def register(app):
    app.add_handler(filters.command("addflyer")(addflyer_handler))
    app.add_handler(filters.command("flyer")(flyer_handler))
    app.add_handler(filters.command("listflyers")(listflyers_handler))
    app.add_handler(filters.command("deleteflyer")(deleteflyer_handler))

