import os
import logging
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatType

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
flyers = db.flyers

def is_admin(user_id, chat):
    # Always allow the group creator (owner)
    if user_id == chat.creator.id if hasattr(chat, "creator") else False:
        return True
    # Check for admin status in the chat
    member = chat.get_member(user_id)
    return member.status in ("administrator", "creator")

def admin_only(func):
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            member = await client.get_chat_member(message.chat.id, message.from_user.id)
            if member.status not in ("administrator", "creator"):
                return await message.reply("❌ You must be an admin to use this command.")
        return await func(client, message, *args, **kwargs)
    return wrapper

@admin_only
async def addflyer_handler(client, message: Message):
    # Accepts /addflyer <name> <caption> with optional attached photo (not reply!)
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.reply("❌ Usage: /addflyer <name> <caption> (optionally attach a photo)")
    name, caption = parts[1], parts[2]
    chat_id = message.chat.id

    photo_id = None
    if message.photo:
        photo_id = message.photo.file_id

    # Save flyer (overwrite if exists)
    flyers.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": {"caption": caption, "photo_id": photo_id}},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' added{' with photo' if photo_id else ' (text only)'}.")

@admin_only
async def changeflyer_handler(client, message: Message):
    # Must reply to a photo OR a text message (for updating either)
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a message with /changeflyer <name> to update flyer image or caption.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /changeflyer <name> (reply to a photo or text to update flyer)")

    name = parts[1]
    chat_id = message.chat.id
    flyer = flyers.find_one({"chat_id": chat_id, "name": name})
    if not flyer:
        return await message.reply(f"❌ No flyer named '{name}' found in this chat.")

    new_caption = flyer.get("caption", "")
    new_photo_id = flyer.get("photo_id", None)

    if message.reply_to_message.photo:
        new_photo_id = message.reply_to_message.photo.file_id
    elif message.reply_to_message.text:
        new_caption = message.reply_to_message.text

    flyers.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": {"caption": new_caption, "photo_id": new_photo_id}},
    )
    await message.reply(f"✅ Flyer '{name}' updated.")

@admin_only
async def deleteflyer_handler(client, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    name = parts[1]
    chat_id = message.chat.id
    result = flyers.delete_one({"chat_id": chat_id, "name": name})
    if result.deleted_count:
        await message.reply(f"✅ Flyer '{name}' deleted.")
    else:
        await message.reply(f"❌ No flyer named '{name}' found in this chat.")

async def flyer_handler(client, message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = parts[1]
    chat_id = message.chat.id
    flyer = flyers.find_one({"chat_id": chat_id, "name": name})
    if not flyer:
        return await message.reply(f"❌ No flyer named '{name}' found in this chat.")
    if flyer.get("photo_id"):
        await message.reply_photo(flyer["photo_id"], caption=flyer["caption"])
    else:
        await message.reply(flyer["caption"])

async def listflyers_handler(client, message: Message):
    chat_id = message.chat.id
    flyer_list = list(flyers.find({"chat_id": chat_id}))
    if not flyer_list:
        return await message.reply("❌ No flyers found in this chat.")
    names = [f"• <b>{f['name']}</b>" for f in flyer_list]
    await message.reply("📋 <b>Flyers in this chat:</b>\n" + "\n".join(names))

def register(app, scheduler=None):
    app.add_handler(filters.command("addflyer")(addflyer_handler))
    app.add_handler(filters.command("changeflyer")(changeflyer_handler))
    app.add_handler(filters.command("deleteflyer")(deleteflyer_handler))
    app.add_handler(filters.command("flyer")(flyer_handler))
    app.add_handler(filters.command("listflyers")(listflyers_handler))
