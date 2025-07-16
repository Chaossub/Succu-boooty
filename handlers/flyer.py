import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or "succubot"
OWNER_ID = 6964994611  # your Telegram user ID

client = MongoClient(MONGO_URI)
flyers_col = client[MONGO_DB]["flyers"]

# --- Admin check decorator ---
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def admin_only(func):
    async def wrapper(client, message: Message):
        # Always let the owner use admin commands
        if message.from_user and message.from_user.id == OWNER_ID:
            return await func(client, message)
        # Only check admin for group chats
        if hasattr(message.chat, "type") and message.chat.type in ("group", "supergroup"):
            if not await is_admin(client, message.chat.id, message.from_user.id):
                return await message.reply("❌ You must be an admin to use this command.")
        else:
            # Private chat: allow
            return await func(client, message)
        return await func(client, message)
    return wrapper

# --- Add flyer ---
@admin_only
async def addflyer_handler(client, message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        return await message.reply("❌ Usage: /addflyer <name> <caption> (attach a photo for image flyer, or leave empty for text-only)")
    flyer_name = args[1].strip().lower()
    flyer_caption = args[2].strip() if len(args) > 2 else ""
    photo_id = None

    # Allow photo from attached or replied image
    if message.photo:
        photo_id = message.photo.file_id
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_id = message.reply_to_message.photo.file_id

    flyers_col.update_one(
        {"chat_id": message.chat.id, "name": flyer_name},
        {"$set": {
            "chat_id": message.chat.id,
            "name": flyer_name,
            "caption": flyer_caption,
            "photo_id": photo_id,
        }},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{flyer_name}' added.")

# --- Get flyer ---
async def getflyer_handler(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    flyer_name = args[1].strip().lower()
    flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": flyer_name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")
    if flyer.get("photo_id"):
        await message.reply_photo(flyer["photo_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", "No text set."))

# --- Delete flyer ---
@admin_only
async def deleteflyer_handler(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    flyer_name = args[1].strip().lower()
    result = flyers_col.delete_one({"chat_id": message.chat.id, "name": flyer_name})
    if result.deleted_count:
        await message.reply(f"✅ Flyer '{flyer_name}' deleted.")
    else:
        await message.reply("❌ Flyer not found.")

# --- List flyers ---
async def listflyers_handler(client, message: Message):
    flyers = flyers_col.find({"chat_id": message.chat.id})
    names = [f"• <b>{f['name']}</b>" for f in flyers]
    if not names:
        return await message.reply("No flyers set yet.")
    await message.reply("<b>Flyers:</b>\n" + "\n".join(names))

# --- Register handlers ---
def register(app):
    app.add_handler(filters.command("addflyer")(addflyer_handler))
    app.add_handler(filters.command("flyer")(getflyer_handler))
    app.add_handler(filters.command("deleteflyer")(deleteflyer_handler))
    app.add_handler(filters.command("listflyers")(listflyers_handler))
