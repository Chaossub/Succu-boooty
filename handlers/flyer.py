import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from utils.check_admin import is_admin

MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["succubot"]
flyers = db["flyers"]

async def addflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.text.split(None, 2)
    if len(args) < 3 and not message.photo:
        return await message.reply("❌ Usage: /addflyer <name> <caption> (attach photo if needed)")
    name = args[1].lower()
    caption = args[2] if len(args) >= 3 else ""
    photo_id = message.photo.file_id if message.photo else None
    flyers.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"caption": caption, "photo_id": photo_id}},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{name}</b> saved!")

async def changeflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /changeflyer <name> (attach photo/caption)")
    name = args[1].lower()
    flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("❌ No flyer found by that name.")
    photo_id = message.photo.file_id if message.photo else flyer.get("photo_id")
    caption = message.caption or flyer.get("caption", "")
    flyers.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": {"caption": caption, "photo_id": photo_id}}
    )
    await message.reply(f"✅ Flyer <b>{name}</b> updated!")

async def deleteflyer_handler(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /deleteflyer <name>")
    name = args[1].lower()
    flyers.delete_one({"chat_id": message.chat.id, "name": name})
    await message.reply(f"✅ Flyer <b>{name}</b> deleted.")

async def listflyers_handler(client, message: Message):
    docs = flyers.find({"chat_id": message.chat.id})
    names = [f"<b>{doc['name']}</b>" for doc in docs]
    if not names:
        return await message.reply("No flyers saved.")
    await message.reply("📝 <b>Flyers:</b>\n" + "\n".join(names))

async def flyer_handler(client, message: Message):
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("❌ Usage: /flyer <name>")
    name = args[1].lower()
    flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        return await message.reply("❌ No flyer found.")
    if flyer.get("photo_id"):
        await message.reply_photo(flyer["photo_id"], caption=flyer["caption"] or "")
    else:
        await message.reply(flyer["caption"] or "(no text)")

def register(app):
    app.add_handler(filters.command("addflyer") & filters.group, addflyer_handler)
    app.add_handler(filters.command("changeflyer") & filters.group, changeflyer_handler)
    app.add_handler(filters.command("deleteflyer") & filters.group, deleteflyer_handler)
    app.add_handler(filters.command("listflyers") & filters.group, listflyers_handler)
    app.add_handler(filters.command("flyer") & filters.group, flyer_handler)
