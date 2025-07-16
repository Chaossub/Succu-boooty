import os
import re
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient
from utils.admin_check import is_admin  # Make sure you have this utility!

MONGO_URI = os.environ["MONGO_URI"]
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["flyer_db"]
flyers = db.flyers

async def admin_guard(client, message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not await is_admin(client, chat_id, user_id):
        await message.reply("❌ You must be an admin to use this command.")
        return False
    return True

async def addflyer_handler(client, message: Message):
    if not await admin_guard(client, message):
        return

    if not message.command or len(message.command) < 2:
        return await message.reply("❌ Usage: <code>/addflyer &lt;name&gt; &lt;caption&gt;</code> (optionally attach a photo)")

    name = message.command[1].lower()
    caption = " ".join(message.command[2:]) if len(message.command) > 2 else ""
    chat_id = message.chat.id

    flyer_data = {
        "chat_id": chat_id,
        "name": name,
        "caption": caption.strip(),
        "type": "text",
    }

    # If photo attached
    if message.photo:
        flyer_data["type"] = "photo"
        flyer_data["file_id"] = message.photo.file_id

    flyers.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": flyer_data},
        upsert=True
    )
    await message.reply(f"✅ Flyer <b>{name}</b> saved!")

async def flyer_handler(client, message: Message):
    if not message.command or len(message.command) < 2:
        return await message.reply("❌ Usage: <code>/flyer &lt;name&gt;</code>")

    name = message.command[1].lower()
    chat_id = message.chat.id
    flyer = flyers.find_one({"chat_id": chat_id, "name": name})

    if not flyer:
        return await message.reply("❌ Flyer not found.")
    if flyer.get("type") == "photo":
        await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", ""))

async def listflyers_handler(client, message: Message):
    chat_id = message.chat.id
    flyer_list = [f["name"] for f in flyers.find({"chat_id": chat_id})]
    if not flyer_list:
        await message.reply("No flyers saved in this group.")
    else:
        await message.reply("Flyers in this group:\n" + "\n".join(f"• <code>{name}</code>" for name in flyer_list))

async def deleteflyer_handler(client, message: Message):
    if not await admin_guard(client, message):
        return

    if not message.command or len(message.command) < 2:
        return await message.reply("❌ Usage: <code>/deleteflyer &lt;name&gt;</code>")

    name = message.command[1].lower()
    chat_id = message.chat.id
    result = flyers.delete_one({"chat_id": chat_id, "name": name})
    if result.deleted_count:
        await message.reply(f"✅ Flyer <b>{name}</b> deleted.")
    else:
        await message.reply("❌ Flyer not found.")

async def changeflyer_handler(client, message: Message):
    if not await admin_guard(client, message):
        return

    if not message.command or len(message.command) < 2:
        return await message.reply("❌ Usage: <code>/changeflyer &lt;name&gt;</code> (with new text/photo attached)")

    name = message.command[1].lower()
    chat_id = message.chat.id
    flyer = flyers.find_one({"chat_id": chat_id, "name": name})
    if not flyer:
        return await message.reply("❌ Flyer not found.")

    # Accept photo or just text
    update_data = {}
    if message.photo:
        update_data = {
            "type": "photo",
            "file_id": message.photo.file_id,
            "caption": message.caption or flyer.get("caption", ""),
        }
    elif message.text and message.text.strip() != f"/changeflyer {name}":
        update_data = {
            "type": "text",
            "caption": message.text.replace(f"/changeflyer {name}", "", 1).strip(),
        }
    else:
        return await message.reply("❌ Reply with new text or photo to update flyer.")

    flyers.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": update_data}
    )
    await message.reply(f"✅ Flyer <b>{name}</b> updated!")

def register(app):
    app.on_message(filters.command("addflyer"))(addflyer_handler)
    app.on_message(filters.command("flyer"))(flyer_handler)
    app.on_message(filters.command("listflyers"))(listflyers_handler)
    app.on_message(filters.command("deleteflyer"))(deleteflyer_handler)
    app.on_message(filters.command("changeflyer"))(changeflyer_handler)
