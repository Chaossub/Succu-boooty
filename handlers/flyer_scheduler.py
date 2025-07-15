# handlers/flyer.py

import os
import logging
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

log = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["succubot"]
flyers_col = db["flyers"]

# Hardcoded group aliases
GROUP_ALIASES = {
    "MODELS_CHAT": -1002884098395,
    "SUCCUBUS_SANCTUARY": -1002823762054,
    "TEST_GROUP": -1002813378700
}

SUPER_ADMIN_ID = 6964994611

def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def flyer_to_caption(flyer):
    cap = f"<b>{flyer['name']}</b>\n"
    if flyer.get('caption'):
        cap += flyer['caption']
    elif flyer.get('text'):
        cap += flyer['text']
    return cap.strip()

def register(app):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ You must be admin to add flyers.")
        if not message.photo:
            return await message.reply("❌ Attach a photo to add a flyer.")
        try:
            args = message.text.split(maxsplit=2)
            if len(args) < 3:
                return await message.reply("❌ Usage: /addflyer <name> <caption>")
            name, caption = args[1], args[2]
            file_id = message.photo.file_id
            flyers_col.replace_one(
                {"name": name},
                {"name": name, "photo": file_id, "caption": caption},
                upsert=True
            )
            await message.reply(f"✅ Flyer '{name}' saved.")
        except Exception as e:
            log.exception("Failed to add flyer")
            await message.reply("❌ Failed to add flyer.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def flyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        name = args[1].strip()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ No flyer found.")
        if "photo" in flyer:
            await message.reply_photo(flyer["photo"], caption=flyer_to_caption(flyer))
        elif "text" in flyer:
            await message.reply(flyer["text"])
        else:
            await message.reply("❌ Flyer is corrupted (no content).")

    @app.on_message(filters.command("addtextflyer") & filters.group)
    async def addtextflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ You must be admin to add flyers.")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("❌ Usage: /addtextflyer <name> <text>")
        name, text = args[1], args[2]
        flyers_col.replace_one(
            {"name": name},
            {"name": name, "text": text},
            upsert=True
        )
        await message.reply(f"✅ Text flyer '{name}' saved.")

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ You must be admin to delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1].strip()
        flyers_col.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    @app.on_message(filters.command("listflyers") & filters.group)
    async def listflyers_handler(client, message: Message):
        flyers = list(flyers_col.find())
        if not flyers:
            return await message.reply("No flyers saved.")
        msg = "\n".join([f"- <b>{f['name']}</b>" for f in flyers])
        await message.reply(msg)

    @app.on_message(filters.command("changeflyer") & filters.group)
    async def changeflyer_handler(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("❌ You must be admin to change flyers.")
        if not message.photo:
            return await message.reply("❌ Attach a new photo as reply.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")
        name = args[1].strip()
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        flyers_col.update_one({"name": name}, {"$set": {"photo": message.photo.file_id}})
        await message.reply(f"✅ Updated image for flyer '{name}'.")

# END OF FILE
